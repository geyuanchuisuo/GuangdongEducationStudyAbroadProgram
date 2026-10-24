"""知识检索接口（独立 /knowledge，2026-10-24 一期；v6.13.0 增 RAG 问答）。

公开接口（客服 Agent 在公开主页使用，与 /cs/faq 同级公开策略）。
- POST /api/v1/knowledge/search：Milvus 混合检索（bge-m3 语义 + BM25 关键词，RRF）；
- POST /api/v1/knowledge/ask(/stream)：智能问答（RAG）——检索 + 直连模型网关
  受限生成回答并附来源；单轮、不落库；不触碰既有客服 Agent 链路。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.schemas.knowledge import KnowledgeAskRequest, KnowledgeSearchRequest
from app.services.knowledge_qa_service import knowledge_qa_service
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


@router.post("/ask", summary="知识库智能问答（RAG，一次性返回）")
async def knowledge_ask(request: KnowledgeAskRequest):
    result = await knowledge_qa_service.ask(request.question, request.top_k)
    return success_response(data=result.model_dump())


@router.post("/ask/stream", summary="知识库智能问答（SSE 流式打字机）")
async def knowledge_ask_stream(request: KnowledgeAskRequest):
    """流式问答（SSE）：event: meta（来源预告）/ token（增量回答）/ done（完整结果）。

    与 /ask 同一服务实现；流式失败自动降级（retrieval_only/unavailable），
    前端必收 done 事件。X-Accel-Buffering: no —— nginx 据此禁用代理缓冲（LOG-097 双保险）。
    """

    async def event_gen():
        async for ev in knowledge_qa_service.ask_stream(request.question, request.top_k):
            name = ev.get("event")
            payload: dict = (
                {"delta": ev["delta"]} if name == "token" else (ev.get("data") or {})
            )
            yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
