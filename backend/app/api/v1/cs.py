from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.database import get_db
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.repositories.course_repo import CourseRepository
from app.schemas.ai import CsFaqOut, CsMessageOut
from app.services.course_service import CourseService
from app.services.cs_agent_service import CS_GREETING

router = APIRouter(prefix="/cs", tags=["公开客服"])


@router.get("/greeting", summary="客服开场白（前端打开客服窗时拉取展示，无需登录）")
async def get_greeting():
    # v6.10.3：Dify opening_statement 仅托管页生效，Service API 不返回；
    # 自研前端打开客服窗时由此接口获取欢迎语，文案与 Dify 应用开场白同源（cs_agent_service.CS_GREETING）
    return success_response(data={"greeting": CS_GREETING})


@router.get("/courses", summary="公开课程列表（课程/项目浏览，无需登录）")
async def list_public_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    category: str | None = Query(None, description="分类筛选"),
    db: AsyncSession = Depends(get_db),
):
    # v6.10.0（v6.9.0 遗留补齐）：复用 M2 课程服务，公开命名空间输出
    service = CourseService(CourseRepository(db))
    return success_response(data=await service.list_courses(page, page_size, category))


@router.get("/policies", summary="公开留学政策资讯（政策内容页数据源，无需登录）")
async def list_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    country: str | None = Query(None, description="国家筛选：德国/新加坡/综合"),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select

    from app.models.course import Policy
    from app.schemas.course import PolicyOut

    q = select(Policy).where(Policy.status == "published")
    cq = select(func.count()).select_from(Policy).where(Policy.status == "published")
    if country:
        q = q.where(Policy.country == country)
        cq = cq.where(Policy.country == country)
    total = (await db.execute(cq)).scalar() or 0
    rows = (await db.execute(
        q.order_by(Policy.publish_date.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return success_response(
        data={
            "items": [PolicyOut.model_validate(r).model_dump() for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


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
