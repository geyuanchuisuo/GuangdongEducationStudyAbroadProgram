from app.core.exceptions import NotFoundError, ValidationError
from app.models.event import EventRegistration
from app.models.user import User
from app.repositories.event_repo import EventRepository
from app.schemas.event import EventOut, RegistrationOut


class EventService:
    def __init__(self, repo: EventRepository):
        self.repo = repo

    async def list_events(self, page: int, page_size: int, status: str | None = None) -> dict:
        total, items = await self.repo.list_events(page, page_size, status=status)
        return {"total": total, "items": [EventOut.model_validate(i).model_dump() for i in items]}

    async def get_event(self, event_id: int) -> dict:
        event = await self.repo.get_event(event_id)
        if not event:
            raise NotFoundError(message="活动不存在")
        return EventOut.model_validate(event).model_dump()

    async def register(self, event_id: int, current_user: User) -> dict:
        event = await self.repo.get_event(event_id)
        if not event:
            raise NotFoundError(message="活动不存在")
        if event.status != "报名中":
            raise ValidationError(message="该活动当前不可报名")
        if event.max_participants and event.current_participants >= event.max_participants:
            raise ValidationError(message="活动名额已满")
        existing = await self.repo.get_registration(event_id, current_user.id)
        if existing:
            raise ValidationError(message="您已报名该活动")

        registration = EventRegistration(event_id=event_id, user_id=current_user.id)
        created = await self.repo.create_registration(registration)
        event.current_participants += 1
        await self.repo.update_event(event)
        return RegistrationOut.model_validate(created).model_dump()
