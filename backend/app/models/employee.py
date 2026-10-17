from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmployeeDailyReport(Base):
    __tablename__ = "employee_daily_report"
    __table_args__ = (
        UniqueConstraint("employee_id", "report_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    report_date = mapped_column(Date, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True, comment="draft/submitted/late_pending")
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否迟报（次日0点后提交或补报通过）")
    create_time = mapped_column(DateTime, server_default=func.now())


class EmployeeTodo(Base):
    __tablename__ = "employee_todo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    todo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium", index=True)
    due_time = mapped_column(DateTime, nullable=True, index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class EmployeeOrg(Base):
    __tablename__ = "employee_org"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("employee_org.id"), nullable=True, index=True)
    org_type: Mapped[str] = mapped_column(String(20), default="department", index=True)
    leader_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DailyReportAnnotation(Base):
    """日报批示：MANAGER 对日报的批注，仅该员工 + MANAGER 可见（v6.4.0）"""
    __tablename__ = "daily_report_annotation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("employee_daily_report.id"), nullable=False, index=True)
    manager_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    create_time = mapped_column(DateTime, server_default=func.now())
