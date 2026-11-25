"""粤教留学 RAG 系统评测主程序（RAGAS 四指标，进程内直调生产代码）。

运行方式（在 evaluation/ 目录下）：
    .venv/Scripts/python.exe run_eval.py                # 全量评测
    .venv/Scripts/python.exe run_eval.py --limit 3      # 只跑前 3 题（冒烟）
    .venv/Scripts/python.exe run_eval.py --skip-ragas   # 只跑检索+生成，落盘 pipeline_raw.json

设计要点：
1. 进程内直调——chdir 到 backend/ 后 import 生产 service（app.config 的 env_file
   是相对路径，必须在 backend/ 下才能加载 .env 里的 deepseek 网关 key）；
   sys.path 注入 backend/ 与 evaluation/，零改业务代码、零改 pyproject。
2. 检索+生成完全复刻生产链路：query_rewriter.rewrite → knowledge_service.search_dual
   (top_k=5) → knowledge_qa_service._build_messages + _chat_gateway。
3. RAGAS 四指标用 deepseek-flash 裁判 + 本机 bge-m3 嵌入。
4. 拒答题（expect_refusal=true）单独评估，不计入四指标均分。
5. 分阶段落盘：pipeline_raw.json（检索+生成，可断点）→ ragas_result.json → summary.json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
RESULTS_DIR = EVAL_DIR / "results"
DATASET = EVAL_DIR / "dataset" / "golden_set.json"

REFUSAL_HINTS = ("未找到", "没有找到", "找不到", "建议联系顾问", "知识库中", "无法回答", "抱歉")


def _bootstrap_path() -> None:
    """切到 backend/ 让 app.config 读到 .env，并把 backend/、evaluation/ 加入 sys.path。"""
    os.chdir(BACKEND_DIR)
    for p in (str(BACKEND_DIR), str(EVAL_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_golden() -> dict:
    with open(DATASET, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 阶段一：检索 + 生成（复刻生产链路）
# ---------------------------------------------------------------------------

async def run_pipeline(golden: dict, limit: int | None) -> list[dict]:
    from app.services.knowledge_qa_service import _build_messages, knowledge_qa_service
    from app.services.knowledge_service import knowledge_service
    from app.services.query_rewriter import query_rewriter

    questions = golden["questions"]
    if limit:
        questions = questions[:limit]

    rows: list[dict] = []
    for idx, case in enumerate(questions, 1):
        q = case["question"]
        row = {
            "id": case["id"],
            "category": case["category"],
            "question": q,
            "ground_truth": case["ground_truth"],
            "relevant_docs": case.get("relevant_docs", []),
            "expect_refusal": case.get("expect_refusal", False),
        }
        try:
            search_query, was_rewritten = await asyncio.to_thread(query_rewriter.rewrite, q)
            retrieval = await asyncio.to_thread(knowledge_service.search_dual, search_query, 5, None)

            row["rewritten_query"] = search_query if was_rewritten else None
            row["was_rewritten"] = was_rewritten
            row["kb_source"] = retrieval.kb_source
            row["retrieved_contexts"] = [it.content for it in retrieval.items]
            row["retrieved_source_files"] = [it.source_file for it in retrieval.items]
            row["retrieved_sources"] = [it.source for it in retrieval.items]
            row["retrieved_scores"] = [it.score for it in retrieval.items]
            row["n_retrieved"] = retrieval.total

            if retrieval.kb_source != "milvus" or not retrieval.items:
                row["answer"] = ""
                row["answer_source"] = "unavailable" if retrieval.kb_source != "milvus" else "retrieval_only"
            else:
                messages = _build_messages(q, retrieval.items)
                try:
                    answer = await knowledge_qa_service._chat_gateway(messages)
                    row["answer"] = answer
                    row["answer_source"] = "model" if answer.strip() else "retrieval_only"
                except Exception as exc:  # noqa: BLE001
                    row["answer"] = ""
                    row["answer_source"] = "gateway_error"
                    row["gen_error"] = str(exc)[:200]
        except Exception as exc:  # noqa: BLE001
            row["error"] = str(exc)[:300]
            row["answer"] = row.get("answer", "")
            row["retrieved_contexts"] = row.get("retrieved_contexts", [])

        rows.append(row)
        flag = row.get("answer_source") or row.get("error", "")
        print(f"  [{idx}/{len(questions)}] id={row['id']} {row['category']} "
              f"命中={row.get('n_retrieved', 0)} source={flag} "
              f"改写={'是' if row.get('was_rewritten') else '否'}")

    with open(RESULTS_DIR / "pipeline_raw.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 检索+生成完成，落盘 results/pipeline_raw.json（{len(rows)} 条）")
    return rows


# ---------------------------------------------------------------------------
# 阶段二：RAGAS 四指标
# ---------------------------------------------------------------------------

def run_ragas(rows: list[dict]) -> dict:
    import ragas_judge
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.run_config import RunConfig

    judge_llm, judge_name = ragas_judge.build_judge_llm()
    embeddings, emb_name = ragas_judge.build_embeddings()
    metrics = ragas_judge.build_metrics()
    print(f"✓ 裁判模型={judge_name}  嵌入模型={emb_name}")

    # 仅对可答题（非拒答 + 有检索上下文 + 有生成回答）跑四指标
    samples, kept = [], []
    for r in rows:
        if r.get("expect_refusal"):
            continue
        if not r.get("retrieved_contexts") or not r.get("answer"):
            continue
        samples.append(SingleTurnSample(
            user_input=r["question"],
            retrieved_contexts=r["retrieved_contexts"],
            response=r["answer"],
            reference=r["ground_truth"],
        ))
        kept.append(r["id"])
    print(f"✓ 参与四指标评测的题目：{len(samples)} 条（ids={kept}）")

    if not samples:
        return {"error": "无有效样本可评测（检索或生成全部失败）"}

    dataset = EvaluationDataset(samples=samples)
    run_config = RunConfig(timeout=240, max_retries=2, max_wait=90, max_workers=4)
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=embeddings,
        run_config=run_config,
    )

    df = result.to_pandas()
    df.to_csv(RESULTS_DIR / "ragas_per_question.csv", index=False, encoding="utf-8-sig")

    # 只取「数值型」的指标得分列：df 里还有 user_input/retrieved_contexts/response/reference
    # 等非数值列（retrieved_contexts 是列表），不能一律 astype(float)。
    def _is_score_col(col: str) -> bool:
        if col in ("user_input", "retrieved_contexts", "response", "reference",
                   "reference_contexts", "retrieved_context_ids", "reference_context_ids"):
            return False
        sample = df[col].dropna()
        if sample.empty:
            return False
        return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in sample)

    metric_cols = [c for c in df.columns if _is_score_col(c)]
    summary_scores = {}
    for c in metric_cols:
        vals = [float(v) for v in df[c].dropna().tolist()]
        summary_scores[c] = round(sum(vals) / len(vals), 4) if vals else None

    out = {
        "judge_model": judge_name,
        "embedding_model": emb_name,
        "evaluated_ids": kept,
        "n_evaluated": len(kept),
        "scores": summary_scores,
        "per_question": df.to_dict(orient="records"),
    }
    with open(RESULTS_DIR / "ragas_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"✓ RAGAS 评测完成，落盘 results/ragas_result.json + ragas_per_question.csv")
    return out


# ---------------------------------------------------------------------------
# 阶段三：拒答题专项 + 汇总
# ---------------------------------------------------------------------------

def run_refusal_and_summary(rows: list[dict], ragas_out: dict) -> dict:
    refusals = [r for r in rows if r.get("expect_refusal")]
    refusal_detail = []
    for r in refusals:
        ans = r.get("answer", "") or ""
        n = r.get("n_retrieved", 0)
        refused = any(h in ans for h in REFUSAL_HINTS) or (r.get("answer_source") == "retrieval_only")
        refusal_detail.append({
            "id": r["id"], "question": r["question"], "n_retrieved": n,
            "answer_source": r.get("answer_source"), "refused_correctly": bool(refused),
            "answer_preview": ans[:120],
        })
    refusal_acc = (sum(1 for d in refusal_detail if d["refused_correctly"]) / len(refusal_detail)) if refusal_detail else None

    # 检索命中率（可答题：检索是否返回了内容）
    answerable = [r for r in rows if not r.get("expect_refusal")]
    hit_rate = (sum(1 for r in answerable if r.get("n_retrieved", 0) > 0) / len(answerable)) if answerable else None
    model_rate = (sum(1 for r in answerable if r.get("answer_source") == "model") / len(answerable)) if answerable else None

    scores = ragas_out.get("scores", {}) if isinstance(ragas_out, dict) else {}

    def g(*names):
        for n in names:
            if n in scores and scores[n] is not None:
                return scores[n]
        return None

    cp = g("context_precision", "llm_context_precision_with_reference")
    cr = g("context_recall", "llm_context_recall")
    fa = g("faithfulness")
    ar = g("answer_relevancy")
    four = [x for x in (cp, cr, fa, ar) if x is not None]
    overall = round(sum(four) / len(four), 4) if four else None

    def grade(v):
        if v is None:
            return "N/A"
        if v >= 0.80:
            return "优秀"
        if v >= 0.60:
            return "良好"
        if v >= 0.40:
            return "一般"
        return "较差"

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_questions": len(rows),
        "answerable": len(answerable),
        "refusal": len(refusals),
        "ragas_scores": {
            "context_precision": cp,
            "context_recall": cr,
            "faithfulness": fa,
            "answer_relevancy": ar,
            "overall": overall,
            "overall_grade": grade(overall),
        },
        "aux_metrics": {
            "retrieval_hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
            "model_answer_rate": round(model_rate, 4) if model_rate is not None else None,
            "refusal_accuracy": round(refusal_acc, 4) if refusal_acc is not None else None,
        },
        "refusal_detail": refusal_detail,
        "judge_model": ragas_out.get("judge_model") if isinstance(ragas_out, dict) else None,
        "embedding_model": ragas_out.get("embedding_model") if isinstance(ragas_out, dict) else None,
    }
    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 56)
    print("  粤教 RAG 评测汇总")
    print("=" * 56)
    print(f"  题目总数：{summary['total_questions']}（可答 {summary['answerable']} / 拒答 {summary['refusal']}）")
    print(f"  裁判模型：{summary['judge_model']}   嵌入：{summary['embedding_model']}")
    print("  🔵 检索质量：")
    print(f"     Context Precision：{_fmt(cp)}  ({grade(cp)})")
    print(f"     Context Recall   ：{_fmt(cr)}  ({grade(cr)})")
    print("  🟢 生成质量：")
    print(f"     Faithfulness     ：{_fmt(fa)}  ({grade(fa)})")
    print(f"     Answer Relevancy ：{_fmt(ar)}  ({grade(ar)})")
    print(f"  📊 综合得分：{_fmt(overall)}  评级：{summary['ragas_scores']['overall_grade']}")
    print("  辅助指标：")
    print(f"     检索命中率：{_fmt(summary['aux_metrics']['retrieval_hit_rate'])}"
          f"   模型作答率：{_fmt(summary['aux_metrics']['model_answer_rate'])}"
          f"   拒答正确率：{_fmt(summary['aux_metrics']['refusal_accuracy'])}")
    print("=" * 56)
    print("✓ 汇总落盘 results/summary.json")
    return summary


def _fmt(v):
    return f"{v:.2%}" if isinstance(v, (int, float)) else "N/A"


async def amain(args) -> None:
    _bootstrap_path()
    golden = _load_golden()
    print(f"✓ 加载黄金题库：{len(golden['questions'])} 题")

    rows = await run_pipeline(golden, args.limit)

    if args.skip_ragas:
        print("--skip-ragas：仅完成检索+生成，未跑 ragas 四指标。")
        return

    ragas_out = run_ragas(rows)
    run_refusal_and_summary(rows, ragas_out)


def main() -> None:
    parser = argparse.ArgumentParser(description="粤教 RAG 系统评测（RAGAS 四指标）")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 题（冒烟用）")
    parser.add_argument("--skip-ragas", action="store_true", help="只跑检索+生成，不调 ragas")
    args = parser.parse_args()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
