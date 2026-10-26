"""问题改写层（v6.14.0）：把口语化/模糊问题改写为适合知识库检索的规范问句。

两级结构（2026-10-24 方案确认）：
1. 智能路由（规则，零延迟）：明显无需改写的直接跳过——超短查询（如 "IHK"、"2+2"，
   防改写破坏专有名词）、已是规范长句问句；
2. DeepSeek 改写（复用 DIFY_MODEL_* 配置，非流式、低温、限长）：改写失败/超时
   → 回退用原问题检索（改写是增强项不是依赖项）。

改写只用于检索（"改写对库"），生成回答时仍用用户原话（"回答对人"）。
独立新增文件：不修改 model_ai_service.py 等 M0 共用代码。
"""

from __future__ import annotations

import re

import httpx

from app.config import settings
from app.utils.logger import logger

_REWRITE_TIMEOUT = httpx.Timeout(15.0, read=10.0)  # deepseek-flash 为推理模型，思考耗时计入读超时

# 推理模型思考块剥离（对齐项目 THINK_RE 模式）
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

# 智能路由：这些情况跳过改写
_MIN_LEN_TO_REWRITE = 6        # 过短问题不改（如 "IHK"、"2+2"），防专有名词被改坏
_MAX_LEN_NORM_QUESTION = 40    # 超过此长度视为已是描述性问句，不再改写

_QUESTION_MARK = re.compile(r"[？?。！!，,、；;\s]")
_HAS_WORD = re.compile(r"[\u4e00-\u9fff]")


def needs_rewrite(question: str) -> bool:
    """智能路由：判断该问题是否值得送模型改写。

    跳过（False）：空/无中文与字母的纯符号、超短（<6 有效字符，专有名词保护）、
    已经是规范问句（含疑问词或问号且长度适中）。
    """
    q = question.strip()
    if not _HAS_WORD.search(q):
        return False
    # 有效字符数（去标点空白）
    effective = _QUESTION_MARK.sub("", q)
    if len(effective) < _MIN_LEN_TO_REWRITE:
        return False
    # 已含疑问结构且不算太模糊：视为规范问句，跳过改写省延迟
    if any(w in q for w in ("什么", "哪些", "怎么", "如何", "多少", "为什么", "吗", "？", "?")):
        return False
    if len(effective) > _MAX_LEN_NORM_QUESTION:
        return False
    return True


_REWRITE_SYSTEM = (
    "你是留学咨询知识库的检索查询改写器。把用户的口语化、模糊问题改写成一句适合"
    "向量库检索的规范中文问句：补全省略的主语和场景词（如项目名、费用、条件、流程），"
    "保留原文的专有名词、数字与代号（如 IHK、2+2、B1）不变；问题本身已清晰时原样返回；"
    "只输出改写后的问题本身，不要解释、不要引号。"
)


class QueryRewriter:
    """DeepSeek 网关改写器；任何失败都回退原问题，绝不阻断检索链路。"""

    def rewrite(self, question: str) -> tuple[str, bool]:
        """返回 (用于检索的问题, 是否发生了改写)。失败一律 (原问题, False)。"""
        if not needs_rewrite(question):
            return question, False
        if not (settings.DIFY_MODEL_API_KEY and settings.DIFY_MODEL_BASE_URL and settings.DIFY_MODEL_NAME):
            return question, False
        try:
            resp = httpx.post(
                settings.DIFY_MODEL_BASE_URL.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DIFY_MODEL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DIFY_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": _REWRITE_SYSTEM},
                        {"role": "user", "content": question},
                    ],
                    "temperature": 0.1,
                    # 不设 max_tokens：deepseek-flash 等推理模型的思考链会计入输出，
                    # 限额会导致思考耗尽配额、content 为空（LOG-117）
                },
                timeout=_REWRITE_TIMEOUT,
            )
            resp.raise_for_status()
            message = resp.json()["choices"][0].get("message", {})
            # 只取 content：reasoning_content 是思考文本（推理模型），作检索问句会污染查询，
            # 不做兜底；content 为空即回退原问题。think 块剥离对齐项目 THINK_RE 模式
            rewritten = (message.get("content") or "").strip()
            rewritten = _THINK_RE.sub("", rewritten).strip().strip("\"'“”")
            if not rewritten or len(rewritten) > 200:
                logger.warning("问题改写输出为空或超长，回退原问题（模型=%s）", settings.DIFY_MODEL_NAME)
                return question, False
            return rewritten, True
        except Exception as exc:  # noqa: BLE001 - 改写是增强项，失败回退原问题
            logger.warning("问题改写失败，回退原问题: %s", exc)
            return question, False


# 模块级单例
query_rewriter = QueryRewriter()
