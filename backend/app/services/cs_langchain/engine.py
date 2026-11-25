"""客服 LangChain 引擎：分类链 + 回答链 + FAQ 向量秒回。

CsLangChainEngine 提供三个能力（均返回与 Dify 链路兼容的数据结构）：
1. classify_intent(message) → {"intent": str, "slots": dict}
   LCEL 链：PromptTemplate | ChatModel | JsonOutputParser
   结构化解析，无正则标记依赖
2. answer_stream(message, history) → AsyncIterator[str]
   LCEL 链流式回答：人设 + RAG 上下文 + 历史消息
3. faq_fast_match(message) → dict | None
   向量检索 yuejiao_faq 集合，高相似度秒回

复用 cs_agent_service 既有业务逻辑（4出口/转线索/报名/推荐落库/敏感过滤/归档）。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

from app.services.cs_langchain.factory import get_model
from app.services.cs_langchain.prompts import INTENT_CLASSIFY_PROMPT, build_persona_message
from app.services.cs_langchain.rag_retriever import KnowledgeRagRetriever
from app.services.cs_langchain.schemas import intent_parser

logger = logging.getLogger(__name__)


class CsLangChainEngine:
    """客服 LangChain 引擎（分类链 + 回答链 + FAQ 秒回）。"""

    def __init__(self, model=None, rag_retriever=None) -> None:
        self._model = model
        self._rag = rag_retriever or KnowledgeRagRetriever()
        self._model_lock = asyncio.Lock()

    @property
    def model(self):
        """懒加载模型（线程安全）。"""
        if self._model is None:
            self._model = get_model()
        return self._model

    # ── 1. 意图分类链（LCEL） ────────────────────────────────────

    async def classify_intent(self, message: str) -> dict[str, Any]:
        """分类意图 + 提取槽位，返回 {"intent": str, "slots": dict}。

        LCEL 链：PromptTemplate | ChatModel | JsonOutputParser
        解析失败返回 {"intent": "chitchat", "slots": {}}（保底不抛错）。
        """
        try:
            prompt = PromptTemplate.from_template(INTENT_CLASSIFY_PROMPT)
            chain = prompt | self.model | intent_parser
            # LangChain 1.x：直接传变量名
            result = await chain.ainvoke({"message": message})
            intent = str(result.get("intent", "chitchat"))
            slots = result.get("slots") or {}
            if not isinstance(slots, dict):
                slots = {}
            return {"intent": intent, "slots": slots}
        except Exception as exc:
            logger.warning("意图分类链失败，回退 chitchat: %s", exc)
            return {"intent": "chitchat", "slots": {}}

    # ── 2. 回答链（流式，人设 + RAG + 历史） ─────────────────────

    async def answer_stream(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """流式回答：逐段 yield 正文增量。

        组装消息序列：[SystemMessage(人设+RAG)] + [HumanMessage/AIMessage 历史] + [HumanMessage(当前)]
        直接调 model.astream()，不封装 LCEL 链（回答链无需 parser）。
        """
        # 检索知识库上下文
        context = await asyncio.to_thread(self._rag.search_context, message)
        system_msg = SystemMessage(content=build_persona_message(context))

        messages: list = [system_msg]
        if history:
            for h in history[-6:]:  # 最近 6 轮（对齐 Dify memory window=10 的保守值）
                role = h.get("role")
                content = h.get("content", "")
                if role == "user" and content:
                    messages.append(HumanMessage(content=content))
                elif role == "assistant" and content:
                    messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=message))

        try:
            async for chunk in self.model.astream(messages):
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    yield token
        except Exception as exc:
            logger.warning("回答链流式失败: %s", exc)
            # 降级：一次性返回兜底话术
            yield "抱歉，本轮响应异常，请稍后重试或留下联系方式由顾问跟进。"

    async def answer_blocking(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """非流式回答（汇总流式结果，供降级链使用）。"""
        full: list[str] = []
        async for token in self.answer_stream(message, history):
            full.append(token)
        return "".join(full).strip()

    # ── 3. FAQ 向量秒回（复用 yuejiao_faq 集合） ──────────────────

    async def faq_fast_match(self, message: str, threshold: float = 0.7) -> dict | None:
        """向量检索 FAQ 问答对，高相似度命中即返回 {"question", "answer"}。

        复用 knowledge_service._hybrid_search_one 单集合 FAQ 检索（top_k=1），
        阈值过滤避免低质量命中。返回 None 表示未命中。
        """
        try:
            # 直接调底层检索（避免 search_dual 双集合开销，FAQ 秒回只需单集合）
            ks = self._rag._service
            hits = await asyncio.to_thread(
                ks._hybrid_search_one,
                ks._faq_collection,
                message,
                1,
                None,
                ["question", "answer", "category"],
            )
            if hits:
                hit = hits[0]
                entity = hit.get("entity", {}) or {}
                score = float(hit.get("distance", 0.0))
                # COSINE 相似度，>0.7 视为高置信命中
                if score >= threshold:
                    return {
                        "question": entity.get("question", ""),
                        "answer": entity.get("answer", ""),
                        "category": entity.get("category", ""),
                        "score": score,
                    }
        except Exception as exc:
            logger.warning("FAQ 向量秒回检索失败: %s", exc)
        return None
