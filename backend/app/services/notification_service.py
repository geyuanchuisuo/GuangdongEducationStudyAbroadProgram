from enum import Enum

from sqlalchemy import select, update, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.system import SysNotification


class NotificationType(str, Enum):
    APPROVAL = "approval"
    TODO = "todo"
    ACADEMIC = "academic"
    PSYCH_ALERT = "psych_alert"
    STATUS = "status"
    SYSTEM = "system"


class NotificationService:
    async def notify(
        self,
        user_id: int,
        type: str | NotificationType,
        title: str,
        content: str | None = None,
        related_type: str | None = None,
        related_id: int | None = None,
    ) -> SysNotification:
        type_str = type.value if isinstance(type, NotificationType) else type

        async with async_session_factory() as session:
            notification = SysNotification(
                user_id=user_id,
                type=type_str,
                title=title,
                content=content,
                related_type=related_type,
                related_id=related_id,
            )
            session.add(notification)
            await session.commit()
            await session.refresh(notification)
            return notification

    async def notify_batch(
        self,
        user_ids: list[int],
        type: str | NotificationType,
        title: str,
        content: str | None = None,
        related_type: str | None = None,
        related_id: int | None = None,
    ) -> int:
        type_str = type.value if isinstance(type, NotificationType) else type
        count = 0

        async with async_session_factory() as session:
            for uid in user_ids:
                notification = SysNotification(
                    user_id=uid,
                    type=type_str,
                    title=title,
                    content=content,
                    related_type=related_type,
                    related_id=related_id,
                )
                session.add(notification)
                count += 1
            await session.commit()
        return count

    async def mark_read(self, notification_id: int, user_id: int) -> bool:
        async with async_session_factory() as session:
            result = await session.execute(
                update(SysNotification)
                .where(SysNotification.id == notification_id, SysNotification.user_id == user_id)
                .values(is_read=True)
            )
            await session.commit()
            return result.rowcount > 0

    async def mark_all_read(self, user_id: int) -> int:
        async with async_session_factory() as session:
            result = await session.execute(
                update(SysNotification)
                .where(SysNotification.user_id == user_id, SysNotification.is_read == False)
                .values(is_read=True)
            )
            await session.commit()
            return result.rowcount

    async def list_for_user(
        self,
        user_id: int,
        type: str | None = None,
        unread_only: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> list[SysNotification]:
        async with async_session_factory() as session:
            stmt = select(SysNotification).where(SysNotification.user_id == user_id)
            if type:
                stmt = stmt.where(SysNotification.type == type)
            if unread_only:
                stmt = stmt.where(SysNotification.is_read == False)
            stmt = stmt.order_by(SysNotification.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_unread(self, user_id: int) -> int:
        async with async_session_factory() as session:
            result = await session.execute(
                select(sa_func.count()).select_from(SysNotification).where(
                    SysNotification.user_id == user_id,
                    SysNotification.is_read == False,
                )
            )
            return result.scalar_one()

    async def count_for_user(
        self,
        user_id: int,
        type: str | None = None,
        unread_only: bool = False,
    ) -> int:
        """按列表筛选条件统计通知总数（供分页 total 使用，不改变既有方法逻辑）"""
        async with async_session_factory() as session:
            stmt = select(sa_func.count()).select_from(SysNotification).where(
                SysNotification.user_id == user_id
            )
            if type:
                stmt = stmt.where(SysNotification.type == type)
            if unread_only:
                stmt = stmt.where(SysNotification.is_read == False)
            result = await session.execute(stmt)
            return result.scalar_one()


notification_service = NotificationService()
