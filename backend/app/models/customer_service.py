from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CsChatSession(Base):
    __tablename__ = "cs_chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户")
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOMER")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_ = mapped_column("metadata", JSON, nullable=True)
    intent_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="意图摘要")
    tags_json = mapped_column(JSON, nullable=True, comment="标签")
    dify_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Dify会话ID")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True, default="web")
    status: Mapped[str] = mapped_column(String(20), default="进行中", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time = mapped_column(DateTime, server_default=func.now())
    end_time = mapped_column(DateTime, nullable=True)


class CsChatMessage(Base):
    __tablename__ = "cs_chat_message"
class CsMessage(Base):
    __tablename__ = "cs_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="命中意图")
    slots_json = mapped_column(JSON, nullable=True, comment="槽位")
    citations_json = mapped_column(JSON, nullable=True, comment="引用知识切片")
    card_data = mapped_column(JSON, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="token消耗")
    created_at = mapped_column(DateTime, server_default=func.now())
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slots = mapped_column(JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsIntentLog(Base):
    __tablename__ = "cs_intent_log"
class CsIntent(Base):
    __tablename__ = "cs_intent"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户")
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    converted: Mapped[bool] = mapped_column(default=False)
    created_at = mapped_column(DateTime, server_default=func.now())
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cs_message.id"), nullable=True, index=True)
    intent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    slots = mapped_column(JSON, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class CsRecommendationLog(Base):
    __tablename__ = "cs_recommend_log"
class CsFaq(Base):
    __tablename__ = "cs_faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_project.id"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event_lecture.id"), nullable=True)
    recommendation_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # course / event
    content = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(default=True, comment="是否启用")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
