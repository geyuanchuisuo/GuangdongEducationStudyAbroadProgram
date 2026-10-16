from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CsChatSession(Base):
    __tablename__ = "cs_chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOMER")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_ = mapped_column("metadata", JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CsChatMessage(Base):
    __tablename__ = "cs_chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    card_data = mapped_column(JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsIntentLog(Base):
    __tablename__ = "cs_intent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    converted: Mapped[bool] = mapped_column(default=False)
    lead_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsFaq(Base):
    __tablename__ = "cs_faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
