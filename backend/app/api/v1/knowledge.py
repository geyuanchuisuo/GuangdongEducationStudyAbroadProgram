"""知识检索接口（独立 /knowledge，2026-10-24 一期）。

公开接口（客服 Agent 在公开主页使用，与 /cs/faq 同级公开策略）。
POST /api/v1/knowledge/search：公司信息/公司业务/留学政策三类资料的
Milvus 混合检索（bge-m3 语义 + BM25 关键词，RRF 融合）。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services.knowledge_service import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识检索"])

VALID_CATEGORIES = {"公司信息", "公司业务", "留学政策"}


@router.post("/search", summary="知识库混合检索")
async def knowledge_search(request: KnowledgeSearchRequest):
    if request.categories:
        unknown = sorted(set(request.categories) - VALID_CATEGORIES)
        if unknown:
            raise BusinessError(
                40002,
                f"未知的知识分类：{'、'.join(unknown)}（可用：{'、'.join(sorted(VALID_CATEGORIES))}）",
            )
    # Milvus/Ollama 客户端为同步实现，放线程池避免阻塞事件循环
    result = await asyncio.to_thread(
        knowledge_service.search, request.query, request.top_k, request.categories
    )
    data = result.model_dump()
    if not request.with_score:
        for item in data["items"]:
            item["score"] = None
    return success_response(data=data)
