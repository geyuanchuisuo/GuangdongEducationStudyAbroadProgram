from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SysEvent(Base):
    __tablename__ = "sys_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at = mapped_column(DateTime, server_default=func.now())


class SysApproval(Base):
    __tablename__ = "sys_approval"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    approval_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    initiator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True)
    approver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SysOperationLog(Base):
    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now(), index=True)


class SysNotification(Base):
    __tablename__ = "sys_notification"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now())
