from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_service import CsChatSession, CsMessage


class CustomerServiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_session(self, session_id: int) -> CsChatSession | None:
        result = await self.db.execute(select(CsChatSession).where(CsChatSession.id == session_id))
        return result.scalar_one_or_none()

    async def create_session(self, user_id: int | None) -> CsChatSession:
        session = CsChatSession(user_id=user_id)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_session(self, session: CsChatSession) -> CsChatSession:
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        intent: str | None = None,
        slots: dict | None = None,
    ) -> CsMessage:
        message = CsMessage(session_id=session_id, role=role, content=content, intent=intent, slots=slots)
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message
