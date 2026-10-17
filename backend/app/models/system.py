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


class ApprovalInstance(Base):
    """审批实例：一次审批请求"""
    __tablename__ = "approval_instance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True, comment="业务类型(leave/convert/late_report/complaint)")
    biz_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联业务ID")
    title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="审批标题")
    initiator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="发起人")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, comment="状态(pending/approved/rejected/cancelled)")
    current_step: Mapped[int] = mapped_column(Integer, default=1, comment="当前审批步骤")
    total_steps: Mapped[int] = mapped_column(Integer, default=1, comment="总审批步骤数")
    finished_at = mapped_column(DateTime, nullable=True, comment="完成时间")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ApprovalTask(Base):
    """审批任务：每个审批节点一条记录"""
    __tablename__ = "approval_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("approval_instance.id"), nullable=False, index=True, comment="审批实例ID")
    approver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="审批人")
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="审批顺序")
    action: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="审批动作(approved/rejected)")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审批意见")
    acted_at = mapped_column(DateTime, nullable=True, comment="操作时间")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, comment="任务状态(pending/completed)")
    created_at = mapped_column(DateTime, server_default=func.now())


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
