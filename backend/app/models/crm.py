from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CrmLead(Base):
    __tablename__ = "crm_lead"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_history = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="新增意向", index=True)
    owner_employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerAssessment(Base):
    __tablename__ = "customer_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_info = mapped_column(JSON, nullable=True)
    assessment_result = mapped_column(JSON, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    matched_products = mapped_column(JSON, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True)
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
