from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.event_repo import EventRepository
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["活动讲座"])


def _get_service(db: AsyncSession = Depends(get_db)) -> EventService:
    return EventService(EventRepository(db))


@router.get("")
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    service: EventService = Depends(_get_service),
):
    return success_response(data=await service.list_events(page, page_size, status))


# 注意：本路由必须声明在 /{event_id} 之前，否则 "my-registrations" 会被当成整数路径参数解析报 422
@router.get("/my-registrations")
async def my_registrations(
    current_user: User = Depends(get_current_user),
    service: EventService = Depends(_get_service),
):
    return success_response(data=await service.my_registrations(current_user))


@router.get("/{event_id}")
async def get_event(event_id: int, service: EventService = Depends(_get_service)):
    return success_response(data=await service.get_event(event_id))


@router.post("/{event_id}/register")
async def register_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    service: EventService = Depends(_get_service),
):
    return success_response(data=await service.register(event_id, current_user), message="报名成功")
