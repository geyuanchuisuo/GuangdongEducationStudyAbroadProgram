from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CsChatSession(Base):
    __tablename__ = "cs_chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True, default="web")
    status: Mapped[str] = mapped_column(String(20), default="进行中", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time = mapped_column(DateTime, server_default=func.now())
    end_time = mapped_column(DateTime, nullable=True)


class CsMessage(Base):
    __tablename__ = "cs_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slots = mapped_column(JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsIntent(Base):
    __tablename__ = "cs_intent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cs_message.id"), nullable=True, index=True)
    intent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    slots = mapped_column(JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsRecommendationLog(Base):
    __tablename__ = "cs_recommend_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_project.id"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event_lecture.id"), nullable=True)
    recommendation_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # course / event
    content = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())
