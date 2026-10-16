from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CrmLead(Base):
    """线索表：记录客户来源和初始录入信息，正式客户数据在 customer 表"""
    __tablename__ = "crm_lead"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户ID")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="线索来源(website/cs/employee)")
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始录入信息")
    background_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="背景信息")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True, comment="线索状态(new/processing/converted/invalid)")
    owner_employee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True, comment="负责员工")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerAssessment(Base):
    """客户研判结果表"""
    __tablename__ = "customer_assessment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户ID")
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="批次号")
    input_source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="输入来源")
    status: Mapped[str] = mapped_column(String(20), default="valid", index=True, comment="有效性(valid/invalid_input/invalid_phone)")
    sg_conclusion: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="新加坡产品结论")
    de_conclusion: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="德国产品结论")
    dimensions_json = mapped_column(JSON, nullable=True, comment="逐维度证据")
    matched_programs_json = mapped_column(JSON, nullable=True, comment="匹配项目")
    recommended_json = mapped_column(JSON, nullable=True, comment="推荐项目与理由")
    missing_info_json = mapped_column(JSON, nullable=True, comment="缺失信息")
    conflicts_json = mapped_column(JSON, nullable=True, comment="冲突项")
    overview: Mapped[str | None] = mapped_column(Text, nullable=True, comment="客户速览")
    follow_up_advice: Mapped[str | None] = mapped_column(Text, nullable=True, comment="跟进建议")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="匹配度评分(90/70/50/20)")
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="提示词版本")
    dify_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Dify运行ID")
    employee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True, index=True, comment="操作员工")
    created_at = mapped_column(DateTime, server_default=func.now())


class CrmFollowUp(Base):
    """客户跟进记录表"""
    __tablename__ = "crm_follow_up"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customer.id"), nullable=False, index=True, comment="关联客户ID")
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="跟进员工")
    follow_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="跟进类型")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="跟进内容")
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True, comment="下一步动作")
    next_date = mapped_column(DateTime, nullable=True, comment="下次跟进日期")
    created_at = mapped_column(DateTime, server_default=func.now())


class AiReport(Base):
    __tablename__ = "ai_report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_content = mapped_column(JSON, nullable=True)
    time_range_start = mapped_column(DateTime, nullable=True, index=True)
    time_range_end = mapped_column(DateTime, nullable=True)
    generated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="generating", index=True)
    created_at = mapped_column(DateTime, server_default=func.now())


class AiReportAttachment(Base):
    __tablename__ = "ai_report_attachment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ai_report.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now())
