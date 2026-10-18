from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import PendingLead
from app.models.customer_service import CsChatMessage, CsChatSession, CsFaq, CsIntentLog, CsRecommendLog


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

    async def add_recommend_log(
        self,
        session_id: int,
        customer_id: int | None = None,
        course_id: int | None = None,
        event_id: int | None = None,
        recommendation_type: str | None = None,
        item_name: str | None = None,
    ) -> CsRecommendLog:
        log = CsRecommendLog(
            session_id=session_id,
            customer_id=customer_id,
            course_id=course_id,
            event_id=event_id,
            recommendation_type=recommendation_type,
            item_name=item_name,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_recommend_logs(self, session_id: int) -> list[CsRecommendLog]:
        result = await self.db.execute(
            select(CsRecommendLog).where(CsRecommendLog.session_id == session_id).order_by(CsRecommendLog.id)
        )
        return list(result.scalars().all())

    # ── 待补全线索（客服对话微信号入口，防重复建档） ──────────
    async def get_pending_lead_by_wechat(self, wechat: str) -> PendingLead | None:
        result = await self.db.execute(
            select(PendingLead).where(PendingLead.wechat == wechat, PendingLead.status == "pending")
        )
        return result.scalar_one_or_none()

    async def create_pending_lead(self, pending: PendingLead) -> PendingLead:
        self.db.add(pending)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending

    # ── 公开客服查询（/cs 路由组） ─────────────────────────
    async def list_faqs(
        self,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
        keyword: str | None = None,
    ) -> tuple[list[CsFaq], int]:
        conditions = [CsFaq.enabled.is_(True)]
        if category:
            conditions.append(CsFaq.category == category)
        if keyword:
            conditions.append(CsFaq.question.like(f"%{keyword}%"))
        count_result = await self.db.execute(select(func.count(CsFaq.id)).where(*conditions))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(CsFaq)
            .where(*conditions)
            .order_by(CsFaq.sort_order, CsFaq.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_messages(self, session_id: int) -> list[CsChatMessage]:
        result = await self.db.execute(
            select(CsChatMessage).where(CsChatMessage.session_id == session_id).order_by(CsChatMessage.id)
        )
        return list(result.scalars().all())
