"""知识库检索适配层：复用 KnowledgeService 双集合混合检索（v6.14.0）。

不新建集合、不重复向量化——直接调用 knowledge_service.search_dual()
（yuejiao_knowledge 长文 + yuejiao_faq 问答对，RRF 融合），返回拼接文本供
LangChain 提示词注入。Milvus/Ollama 不可用时返回空串（不抛异常）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KnowledgeRagRetriever:
    """KnowledgeService 双集合检索的轻量适配（同步实现，调用方用 to_thread 包装）。"""

    def __init__(self, knowledge_service=None) -> None:
        # 延迟导入避免循环依赖
        if knowledge_service is None:
            from app.services.knowledge_service import knowledge_service as _ks
            knowledge_service = _ks
        self._service = knowledge_service

    def search_context(self, query: str, top_k: int = 3) -> str:
        """检索知识库，返回拼接后的上下文文本（空串表示无结果或不可用）。"""
        try:
            result = self._service.search_dual(query, top_k=top_k)
            if result.items:
                parts = []
                for item in result.items:
                    cat = f"[{item.category}] " if item.category else ""
                    parts.append(cat + item.content)
                return "\n\n".join(parts)
        except Exception as exc:
            logger.warning("客服 RAG 检索不可用（Milvus/Ollama）: %s", exc)
        return ""
