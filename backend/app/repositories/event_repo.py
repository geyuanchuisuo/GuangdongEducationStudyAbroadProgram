from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventLecture, EventRegistration


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_events(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[int, list[EventLecture]]:
        query = select(EventLecture)
        count_query = select(func.count(EventLecture.id))
        if status is not None:
            query = query.where(EventLecture.status == status)
            count_query = count_query.where(EventLecture.status == status)
        query = query.order_by(EventLecture.id.desc()).offset((page - 1) * page_size).limit(page_size)
        total = (await self.db.execute(count_query)).scalar_one()
        items = (await self.db.execute(query)).scalars().all()
        return total, list(items)

    async def get_event(self, event_id: int) -> EventLecture | None:
        result = await self.db.execute(select(EventLecture).where(EventLecture.id == event_id))
        return result.scalar_one_or_none()

    async def get_registration(self, event_id: int, user_id: int) -> EventRegistration | None:
        result = await self.db.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_registration(self, registration: EventRegistration) -> EventRegistration:
        self.db.add(registration)
        await self.db.commit()
        await self.db.refresh(registration)
        return registration

    async def update_event(self, event: EventLecture) -> EventLecture:
        await self.db.commit()
        await self.db.refresh(event)
        return event
