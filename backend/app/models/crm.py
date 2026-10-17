from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 客户状态机：一期采用 4 态，预留 6 态扩展位（二期新增：意向强烈/已签约/已入学）。
LEAD_STATUS_NEW = "新增意向"
LEAD_STATUS_FOLLOWING = "跟进中"
LEAD_STATUS_CONVERTED = "已转化"
LEAD_STATUS_LOST = "已流失"

LEAD_STATUSES: tuple[str, ...] = (
    LEAD_STATUS_NEW,
    LEAD_STATUS_FOLLOWING,
    LEAD_STATUS_CONVERTED,
    LEAD_STATUS_LOST,
)

# 一期合法状态流转（源状态 -> 允许到达的目标状态）。终态（已转化/已流失）不可再流转。
LEAD_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    LEAD_STATUS_NEW: (LEAD_STATUS_FOLLOWING, LEAD_STATUS_LOST),
    LEAD_STATUS_FOLLOWING: (LEAD_STATUS_CONVERTED, LEAD_STATUS_LOST),
}


class CrmLead(Base):
    __tablename__ = "crm_lead"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True, default="客服")
    profile = mapped_column(JSON, nullable=True)
    follow_up_history = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=LEAD_STATUS_NEW, index=True)
    owner_employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerAssessment(Base):
    __tablename__ = "customer_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    lead_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crm_lead.id"), nullable=True, index=True)
    extracted_info = mapped_column(JSON, nullable=True)
    assessment_result = mapped_column(JSON, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    matched_products = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    invalid_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class AiReport(Base):
    __tablename__ = "ai_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_content = mapped_column(JSON, nullable=True)
    time_range_start = mapped_column(DateTime, nullable=True, index=True)
    time_range_end = mapped_column(DateTime, nullable=True)
    generated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="generating", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
