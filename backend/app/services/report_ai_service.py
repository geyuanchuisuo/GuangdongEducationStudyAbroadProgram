"""M5 智能报告模块 — 阶段 5：报告专用 AI 分析入口（v6.11.0 口径）

需求确认（2026-10-18）§2.7 明确：
1. 一期必须接入**报告专用** AI，且必须经公共 AI 网关调用，不得直连 Dify、
   不得复用客服/学生/员工 Agent；
2. 没有专用配置时视为交付阻塞/不可用，**不得把 mock 文本标成真实 AI**；
3. AI 只做文字归纳（摘要/趋势/分析/建议），数字一律由程序计算；
4. schema 校验、超时/错误处理；失败时确定性指标仍保留。

实现：
- 优先调用公共网关的报告 Agent（`AgentType.REPORT`，由 M0 在 ai_service.py 登记，
  配置项 `DIFY_REPORT_AGENT_KEY`）——**M0 当前尚未登记该 Agent，属上游阻塞项**，
  未登记时 AI 直接标「不可用」，不回落模型网关、不伪造；
- 仅当 `REPORT_DATA_SOURCE=mock`（演示/测试环境）才允许本地模拟文本，并标 `ai_source=mock`。
"""
import json
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

PROMPT_VERSION = "REPORT-v1.0"

_KEYS = ("summary", "trend", "analysis", "suggestions")


def _suggestion(text: str) -> dict:
    return {"content": text, "department": None, "owner": None}


def _mock_analysis(report_type: str, metrics: dict) -> dict:
    """本地模拟输出（仅演示/测试环境可用，报告中标 ai_source=mock）。"""
    if report_type == "customer_analysis":
        if metrics.get("status_overview") is None:
            return {
                "summary": "（模拟）本期期末状态不可得，仅展示可确定的新增客户数量。",
                "trend": None,
                "analysis": "（模拟）客户状态类指标因缺少历史时点数据标记为数据不可得。",
                "suggestions": [_suggestion("（模拟）推动 M1 提供周期末状态与历史研判能力")],
            }
        total = metrics["status_overview"]["total"]
        intent = metrics["status_overview"]["intent"]
        return {
            "summary": f"（模拟）期末客户 {total} 名，其中意向客户 {intent} 名。",
            "trend": None,
            "analysis": "（模拟）本期新增客户来自多渠道，意向占比保持稳定。",
            "suggestions": [_suggestion("（模拟）优先跟进信息不足客户的研判补全")],
        }

    if report_type == "daily_report_summary":
        days = metrics["days"]
        total_submitted = sum(d["submitted"] for d in days)
        total_missing = sum(d["missing"] for d in days)
        missing_days = "、".join(d["date"] for d in days if d["missing"] > 0) or "无"
        return {
            "summary": (
                f"（模拟）本日报周期共统计 {len(days)} 个工作日，"
                f"已提交 {total_submitted} 人次、未提交 {total_missing} 人次。"
            ),
            "trend": None,
            "analysis": f"（模拟）存在未提交的日期：{missing_days}。",
            "suggestions": [_suggestion("（模拟）跟进未提交日报的部门")],
        }

    if report_type == "weekly_report_summary":
        total = metrics["week_total"]
        depts = metrics["departments"]
        missing_depts = "、".join(
            f"{name}（{d['missing']} 人次）" for name, d in depts.items() if d["missing"] > 0
        ) or "无"
        return {
            "summary": (
                f"（模拟）本周应交 {total['should_submit']} 人次、已交 {total['submitted']} 人次、"
                f"未交 {total['missing']} 人次。"
            ),
            "trend": None,
            "analysis": f"（模拟）缺报集中在：{missing_depts}。",
            "suggestions": [_suggestion("（模拟）按部门跟进缺报情况")],
        }

    if report_type == "psych_weekly":
        risk = metrics["risk"]
        return {
            "summary": (
                f"（模拟）本周覆盖学生 {metrics['covered_students']} 人，"
                f"高风险 {risk.get('高', 0)} 人。"
            ),
            "trend": None,
            "analysis": "（模拟）整体情绪态势平稳，个别学生需持续关注。",
            "suggestions": [_suggestion("（模拟）对高风险学生安排一对一关怀")],
        }

    if report_type == "complaint_weekly":
        if not metrics.get("orders_total"):
            return {
                "summary": "（模拟）本周期无工单记录。",
                "trend": None,
                "analysis": "（模拟）无工单数据，无法分析投诉趋势。",
                "suggestions": [_suggestion("（模拟）确认工单来源系统是否正常")],
            }
        sat = metrics.get("satisfaction") or {}
        return {
            "summary": (
                f"（模拟）本期工单 {metrics.get('orders_total', 0)} 条，"
                f"其中投诉 {metrics.get('new_count', 0)} 条，"
                f"待分析 {metrics.get('pending_analysis', 0)} 条。"
            ),
            "trend": None,
            "analysis": (
                f"（模拟）满意度：满意 {sat.get('满意', 0)}、不满意 {sat.get('不满意', 0)}、"
                f"未评价 {sat.get('未评价', 0)}。"
            ),
            "suggestions": [_suggestion("（模拟）优先处理长期未解决与未响应投诉")],
        }

    raise ValueError(f"未知报告类型: {report_type}")


def _validate(analysis: dict | None) -> dict | None:
    """AI 输出结构校验：缺失/类型不符视为失败（不得把半成品当真实结果）。"""
    if not isinstance(analysis, dict):
        return None
    if not all(k in analysis for k in _KEYS):
        return None
    if not isinstance(analysis["summary"], str) or not isinstance(analysis["analysis"], str):
        return None
    if not isinstance(analysis["suggestions"], list):
        return None
    return analysis


def _strip_reasoning(text: str) -> str:
    """剥离推理模型思考块（v6.11.1）。

    真实 Dify 报告 Agent（deepseek 系）会在正文前输出
    `<think>…</think>` + `<!--dify-deepseek-reasoning-->` 注释，
    思考块里可能出现花括号，直接取首个 `{` 可能截到思考内容 → 必须先剥离。
    """
    if not text:
        return ""
    out = text
    for tag in ("think", "thinking", "reasoning"):
        while True:
            start = out.lower().find(f"<{tag}>")
            if start < 0:
                break
            end = out.lower().find(f"</{tag}>", start)
            if end < 0:
                out = out[:start]
                break
            out = out[:start] + out[end + len(f"</{tag}>"):]
    # 去掉 <!-- … --> 注释（含 dify-deepseek-reasoning 标记）
    while True:
        s = out.find("<!--")
        if s < 0:
            break
        e = out.find("-->", s)
        if e < 0:
            out = out[:s]
            break
        out = out[:s] + out[e + 3:]
    return out


def _parse_json(text: str) -> dict | None:
    """从模型输出中提取 JSON（容忍思考块、```json 围栏与前后缀说明）。"""
    raw = _strip_reasoning(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    # 优先整体解析，失败再退化为「首 { 到末 }」切片
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:  # noqa: BLE001
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        return None


class ReportAIService:
    """报告 AI 分析入口（报告专用 Agent，经公共 AI 网关）。

    `source`：`dify`=报告专用 Agent 成功 / `mock`=演示环境模拟 / `unavailable`=不可用。
    """

    def __init__(self) -> None:
        self.source: str = "unavailable"
        self.prompt_version: str = PROMPT_VERSION

    def _build_prompt(self, report_type: str, metrics: dict, context: dict | None) -> str:
        payload = {"report_type": report_type, "metrics": metrics, "context": context or {}}
        return (
            "你是粤教留学项目的智能报告分析助手。只能基于给定指标与上下文归纳文字，"
            "禁止自行计算或改写任何数字、禁止编造事实与时长、禁止评价个人绩效、"
            "禁止引用工单原文作为判断理由。\n"
            "严格输出 JSON，字段为 summary（字符串）、trend（字符串或 null）、"
            "analysis（字符串）、suggestions（数组，元素为字符串）。不要输出 Markdown。\n"
            f"输入：{json.dumps(payload, ensure_ascii=False)}"
        )

    async def analyze(
        self, report_type: str, metrics: dict, context: dict | None = None
    ) -> dict | None:
        # 1) 报告专用 Agent（经公共网关）；M0 未登记 REPORT 时直接判不可用
        try:
            from app.services.ai_service import AgentType, ai_service

            agent = getattr(AgentType, "REPORT", None)
            if agent is not None:
                # v6.11.3：报告分析是单轮无状态调用，session 必须传 "new"。
                # 曾传 f"report-{type}-{ts}" 被网关当作 conversation_id 发给 Dify，
                # Dify 校验 conversation_id 必须是 UUID → 400 invalid_param。
                resp = await ai_service.chat(
                    agent,
                    self._build_prompt(report_type, metrics, context),
                    "new",
                    user_id="report",
                )
                analysis = _parse_json(getattr(resp, "content", ""))
                if isinstance(analysis, dict) and isinstance(analysis.get("suggestions"), list):
                    analysis["suggestions"] = [
                        _suggestion(item) if isinstance(item, str) else item
                        for item in analysis["suggestions"]
                    ]
                validated = _validate(analysis)
                if validated:
                    self.source = "dify"
                    return validated
        except Exception as exc:  # noqa: BLE001 — AI 失败不阻断确定性报告
            logger.warning("报告专用 Agent 调用失败: type=%s error=%s", report_type, exc)

        # 2) 演示/测试环境才允许模拟文本；生产环境标注不可用
        if settings.REPORT_DATA_SOURCE == "mock":
            try:
                mock = _validate(_mock_analysis(report_type, metrics))
                if mock:
                    self.source = "mock"
                    return mock
            except Exception as exc:  # noqa: BLE001
                logger.warning("报告模拟分析失败: type=%s error=%s", report_type, exc)

        self.source = "unavailable"
        return None
