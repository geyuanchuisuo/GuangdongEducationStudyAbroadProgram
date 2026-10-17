from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# SQLite 仅 INTEGER PRIMARY KEY 自增；用 with_variant 让测试(SQLite)退化为 INTEGER，生产(MySQL)仍为 BIGINT
BigInt = BigInteger().with_variant(Integer, "sqlite")


class CsChatSession(Base):
    """客服会话表：公开客服允许匿名访客（user_id 可空），关联正式客户 customer。"""

    __tablename__ = "cs_chat_session"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户")
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOMER")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_ = mapped_column("metadata", JSON, nullable=True)
    intent_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="意图摘要")
    tags_json = mapped_column(JSON, nullable=True, comment="标签")
    dify_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Dify会话ID")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CsChatMessage(Base):
    __tablename__ = "cs_chat_message"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="命中意图")
    slots_json = mapped_column(JSON, nullable=True, comment="槽位")
    citations_json = mapped_column(JSON, nullable=True, comment="引用知识切片")
    card_data = mapped_column(JSON, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="token消耗")
    created_at = mapped_column(DateTime, server_default=func.now())


class CsIntentLog(Base):
    __tablename__ = "cs_intent_log"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户")
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    converted: Mapped[bool] = mapped_column(default=False)
    created_at = mapped_column(DateTime, server_default=func.now())


class CsRecommendLog(Base):
    """推荐日志表：客服 Agent 每次课程/活动推荐落库（阶段4，供转化统计与 M5 取数）。"""

    __tablename__ = "cs_recommend_log"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInt, ForeignKey("cs_chat_session.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户")
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_project.id"), nullable=True, comment="推荐课程ID")
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event_lecture.id"), nullable=True, comment="推荐活动ID")
    recommendation_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="推荐类型(course/event/other)")
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="推荐项名称")
    created_at = mapped_column(DateTime, server_default=func.now())


class CsFaq(Base):
    __tablename__ = "cs_faq"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(default=True, comment="是否启用")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
