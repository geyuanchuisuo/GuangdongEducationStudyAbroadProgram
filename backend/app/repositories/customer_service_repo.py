from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_service import CsChatMessage, CsChatSession, CsIntentLog


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
        card_data: dict | None = None,
    ) -> CsChatMessage:
        message = CsChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            slots_json=slots,
            card_data=card_data,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def count_messages(self, session_id: int, role: str = "user") -> int:
        result = await self.db.execute(
            select(func.count(CsChatMessage.id)).where(
                CsChatMessage.session_id == session_id, CsChatMessage.role == role
            )
        )
        return result.scalar_one()

    async def add_intent_log(
        self,
        session_id: int,
        user_id: int | None,
        customer_id: int | None,
        intent_type: str,
        confidence: float | None = None,
        converted: bool = False,
    ) -> CsIntentLog:
        log = CsIntentLog(
            session_id=session_id,
            user_id=user_id,
            customer_id=customer_id,
            intent_type=intent_type,
            confidence=confidence,
            converted=converted,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log
