from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# SQLite 仅 INTEGER PRIMARY KEY 自增；用 with_variant 让测试(SQLite)退化为 INTEGER，生产(MySQL)仍为 BIGINT
BigInt = BigInteger().with_variant(Integer, "sqlite")


class CrmLead(Base):
    """线索表：记录客户来源和初始录入信息，正式客户数据在 customer 表"""
    __tablename__ = "crm_lead"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户ID")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="线索来源(website/cs/employee)")
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始录入信息")
    background_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="背景信息")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True, comment="线索状态(new/processing/converted/invalid)")
    owner_employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True, comment="负责员工")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomerAssessment(Base):
    """客户研判结果表"""
    __tablename__ = "customer_assessment"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, index=True, comment="关联客户ID")
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
    employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True, comment="操作员工")
    created_at = mapped_column(DateTime, server_default=func.now())


class CrmFollowUp(Base):
    """客户跟进记录表"""
    __tablename__ = "crm_follow_up"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=False, index=True, comment="关联客户ID")
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True, comment="跟进员工")
    follow_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="跟进类型")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="跟进内容")
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True, comment="下一步动作")
    next_date = mapped_column(DateTime, nullable=True, comment="下次跟进日期")
    created_at = mapped_column(DateTime, server_default=func.now())


class AiReport(Base):
    __tablename__ = "ai_report"
    # M5-06.4 版本号并发保护：同类型同周期版本号唯一（冲突由仓储层捕获重试）
    __table_args__ = (
        UniqueConstraint(
            "report_type", "time_range_start", "time_range_end", "version",
            name="uq_ai_report_version",
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_content = mapped_column(JSON, nullable=True)
    time_range_start = mapped_column(DateTime, nullable=True, index=True)
    time_range_end = mapped_column(DateTime, nullable=True)
    generated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="generating", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号（同类型同周期递增）")
    data_source_status: Mapped[str] = mapped_column(String(20), default="mock", comment="数据来源状态(mock/production)")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="生成失败原因")
    created_at = mapped_column(DateTime, server_default=func.now())


class AiReportAttachment(Base):
    __tablename__ = "ai_report_attachment"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInt, ForeignKey("ai_report.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now())


class AiReportDrill(Base):
    """报告下钻快照（v6.11.0 §2.2/§五）。

    生成报告时把授权下钻数据一并固化，**旧报告的详情/下钻/PDF 永不再查实时库**；
    心理个案与投诉特别案例的敏感原文按用户确认入库（仅授权接口可读）。
    """
    __tablename__ = "ai_report_drill"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("ai_report.id"), nullable=False, index=True, comment="所属报告"
    )
    drill_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="customers / psych_cases / special_cases"
    )
    payload = mapped_column(JSON, nullable=False, comment="下钻行快照（含授权后可见字段）")
    row_count: Mapped[int] = mapped_column(Integer, default=0, comment="快照行数")
    created_at = mapped_column(DateTime, server_default=func.now())


class TicketAIAnalysis(Base):
    """投诉工单 AI 分析记录（v6.11.0 §2.6）。

    独立于 M4 工单表：只保存 AI 分析结论与来源，不改 M4 任何表结构。
    一次工单只保留最近一次成功分析（status=succeeded），失败/待分析也留痕。
    """
    __tablename__ = "ticket_ai_analysis"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True, comment="M4 工单ID（仅引用不建外键）")
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="AI 分类：投诉/建议/咨询")
    low_satisfaction_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="AI 归纳摘要（不得引用原文）")
    special_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="特别案例归纳理由")
    model_source: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="模型/来源标识")
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始输出（排障用，接口不外泄）")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, comment="pending / succeeded / failed"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now())