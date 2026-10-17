import json
import logging
from typing import Any, Callable, Awaitable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.system import SysEvent
from app.services.event_contracts import EVENT_CONTRACTS, EventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(
        self,
        event_type: str | EventType,
        source_module: str,
        payload: dict[str, Any],
    ) -> int:
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str in EVENT_CONTRACTS:
            contract = EVENT_CONTRACTS[event_type_str]
            for field in contract["fields"]:
                if field not in payload:
                    logger.warning(
                        "Event %s missing contract field '%s', payload: %s",
                        event_type_str,
                        field,
                        payload,
                    )

        async with async_session_factory() as session:
            event = SysEvent(
                event_type=event_type_str,
                source_module=source_module,
                payload=payload,
                status="pending",
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            event_id = event.id

        await self._dispatch(event_type_str, payload)

        return event_id  # type: ignore[return-value]

    async def _dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                await handler(payload)
            except Exception:
                logger.exception("Event handler failed: event=%s handler=%s", event_type, handler.__name__)

        async with async_session_factory() as session:
            await session.execute(
                update(SysEvent)
                .where(SysEvent.event_type == event_type, SysEvent.status == "pending")
                .values(status="consumed")
            )
            await session.commit()

    async def get_pending(self, event_type: str | None = None, limit: int = 50) -> list[SysEvent]:
        async with async_session_factory() as session:
            stmt = select(SysEvent).where(SysEvent.status == "pending")
            if event_type:
                stmt = stmt.where(SysEvent.event_type == event_type)
            stmt = stmt.order_by(SysEvent.created_at).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())


event_bus = EventBus()
