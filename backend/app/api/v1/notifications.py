from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["通知中心"])


@router.get("", summary="通知列表")
async def list_notifications(
    type: str | None = Query(None, description="通知类型"),
    unread_only: bool = Query(False, description="仅未读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    items = await notification_service.list_for_user(
        current_user.id,
        type=type,
        unread_only=unread_only,
        offset=offset,
        limit=page_size,
    )
    total = await notification_service.count_for_user(
        current_user.id, type=type, unread_only=unread_only
    )
    return success_response(
        data={
            "items": [NotificationOut.model_validate(n) for n in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/unread-count", summary="未读数量")
async def unread_count(current_user: User = Depends(get_current_user)):
    count = await notification_service.count_unread(current_user.id)
    return success_response(data={"count": count})


@router.put("/read-all", summary="全部标记已读")
async def mark_all_read(current_user: User = Depends(get_current_user)):
    count = await notification_service.mark_all_read(current_user.id)
    return success_response(data={"count": count}, message="已全部标记为已读")


@router.put("/{notification_id}/read", summary="标记单条已读")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
):
    ok = await notification_service.mark_read(notification_id, current_user.id)
    if not ok:
        raise NotFoundError(message="通知不存在或无权操作")
    return success_response(data={"id": notification_id}, message="已标记为已读")
