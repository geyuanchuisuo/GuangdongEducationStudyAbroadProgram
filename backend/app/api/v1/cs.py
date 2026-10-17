from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.database import get_db
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import CsFaqOut, CsMessageOut

router = APIRouter(prefix="/cs", tags=["公开客服"])


@router.get("/faq", summary="公开 FAQ 列表（常见问题自助解答，无需登录）")
async def list_faqs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: str | None = Query(None, description="分类筛选"),
    keyword: str | None = Query(None, description="问题关键词"),
    db: AsyncSession = Depends(get_db),
):
    repo = CustomerServiceRepository(db)
    items, total = await repo.list_faqs(page, page_size, category=category, keyword=keyword)
    return success_response(
        data={
            "items": [CsFaqOut.model_validate(i).model_dump() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/sessions/{session_id}/messages", summary="客服会话消息历史（公开客服允许匿名凭会话ID查询）")
async def list_session_messages(session_id: int, db: AsyncSession = Depends(get_db)):
    repo = CustomerServiceRepository(db)
    session = await repo.get_session(session_id)
    if not session:
        raise NotFoundError(message="会话不存在")
    messages = await repo.list_messages(session_id)
    return success_response(data=[CsMessageOut.model_validate(m).model_dump() for m in messages])
