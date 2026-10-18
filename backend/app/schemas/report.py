"""M5 智能报告模块 — 统一报告输入契约（数据契约）

报告逻辑只消费本文件定义的标准输入结构，不直接依赖 M1-M4 业务表。
模拟数据提供器与后续真实数据适配器都输出此结构，替换时只换提供器，
指标计算、报告模板、权限、PDF 脱敏逻辑均不变。

口径依据：promts/智能报告/report_package/03_模拟数据设计与验证方案V1.md
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── 枚举常量 ──────────────────────────────────────────────

# 客户状态（6 态），与接口契约 §0.5 一致
CustomerStatus = Literal["NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST"]

# 画像结论四分类（v6.11.0 需求确认 §2.3：四类独立，partial 不再并入「信息不足」）
# matched→符合 / partial→部分符合 / not_matched→不符合 / pending→信息不足
ProfileConclusion = Literal["符合", "部分符合", "不符合", "信息不足"]

# 投诉工单类型（只有"投诉"计入投诉周报，建议/咨询排除）
FeedbackType = Literal["投诉", "建议", "咨询"]

# 投诉满意度
Satisfaction = Literal["满意", "不满意", "未评价"]

# 流失来源（自动流失=系统规则 90 天未登录且无员工提交；人工流失=员工标记）
LossSource = Literal["auto", "manual"]

# 心理风险等级（沿用学生模块识别结果）
PsychRiskLevel = Literal["低", "中", "高"]


# ── 四类报告统一输入 ──────────────────────────────────────

class CustomerReportInput(BaseModel):
    """客户经营分析的统一输入。

    注意：一个手机号对应一条有效客户；若出现同手机号多条记录，由计算器按手机号去重。
    """
    customer_id: int
    phone: str
    name: str
    source_channel: str
    # 新增时间取两者中更早者：first_register_login_at / first_employee_submit_at
    first_register_login_at: datetime | None = None
    first_employee_submit_at: datetime | None = None
    # 期末状态：**周期结束时**的客户状态（6 态）。
    # v6.11.0：M1 尚无历史时点能力，生产取数不得用当前值冒充期末值 →
    # 不可得时置 None，由计算器把依赖状态的指标标记「数据不可得」。
    status_at_period_end: CustomerStatus | None = None
    # 流失来源：仅 status=LOST 时有意义，其余为 None
    status_source: LossSource | None = None
    # 是否回流客户（曾流失后回流，不计入本期新增）
    reflowed: bool = False
    # 最新有效研判时间与结论
    latest_assessment_at: datetime | None = None
    sg_conclusion: ProfileConclusion | None = None
    de_conclusion: ProfileConclusion | None = None
    owner_employee_id: int | None = None
    follow_up_summary: str | None = None


class EmployeeInput(BaseModel):
    """员工花名册（用于日报/周报的"应提交人数"统计，含未提交者）。"""
    employee_id: int
    department: str
    employment_status: Literal["active", "inactive"] = "active"


class EmployeeDailyReportInput(BaseModel):
    """员工日报的统一输入（用于日报汇总与周报汇总）。"""
    employee_id: int
    department: str
    # 日报所属业务日期（补交归回原日期）
    report_date: date
    submitted_at: datetime
    content: str
    is_valid: bool = True


class PsychReportInput(BaseModel):
    """学生心理记录的统一输入（统计对象为本周有心理相关记录的学生）。"""
    student_id: int
    record_at: datetime
    emotion_tag: str | None = None
    risk_level: PsychRiskLevel | None = None
    feedback_summary: str | None = None
    responsible_employee_id: int | None = None
    has_psych_record: bool = True
    # v6.11.0 §2.5：心理个案授权后可看完整详情（身份/联系方式/反馈原文），依赖 M4 提供
    student_name: str | None = None
    student_contact: str | None = None
    feedback_raw: str | None = None


class ComplaintReportInput(BaseModel):
    """投诉工单的统一输入（仅 feedback_type=投诉 计入）。"""
    ticket_id: int
    student_id: int
    feedback_type: FeedbackType
    # 类型来源标识（v6.11.0 §2.6）：student=学生所选、ai=AI 分类、unknown=未分类
    category_source: Literal["student", "ai", "unknown"] = "unknown"
    submitted_at: datetime
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None
    status: Literal["open", "resolved"] = "open"
    satisfaction: Satisfaction = "未评价"
    # AI 低评分 / 高风险候选（v6.11.0：一期无人工复核，特别案例由 AI 判定）
    ai_low_score: bool = False
    ai_high_risk: bool = False
    # 保留字段仅为兼容旧数据；一期判定不再要求人工复核
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    reviewer_id: int | None = None
    owner_id: int | None = None
    progress: str | None = None
    # AI 分析记录（v6.11.0 §2.6）：analyzed=已有成功分析；pending=待分析；failed=分析失败
    analysis_status: Literal["analyzed", "pending", "failed"] = "pending"
    analysis_record_id: int | None = None
    ai_summary: str | None = None
    # 工单原文（v6.11.0：投诉特别案例在 MANAGER 权限下允许完整详情，快照需固化原文）
    content: str | None = None
    detail: str | None = None
    # 学生身份/联系方式（依赖 M4 提供；缺失为 None，不伪造）
    student_name: str | None = None
    student_contact: str | None = None


# ── 模拟数据包 ────────────────────────────────────────────

class MockReportDataset(BaseModel):
    """模拟数据包：带模拟标记、数据更新时间、参考周期与四类输入。"""
    is_mock: bool = True
    data_updated_at: datetime
    period_start: datetime
    period_end: datetime
    customers: list[CustomerReportInput] = Field(default_factory=list)
    employees: list[EmployeeInput] = Field(default_factory=list)
    daily_reports: list[EmployeeDailyReportInput] = Field(default_factory=list)
    psych_records: list[PsychReportInput] = Field(default_factory=list)
    complaints: list[ComplaintReportInput] = Field(default_factory=list)


# ── 报告类型与接口 ────────────────────────────────────────

# 五类报告（接口契约 §7）
ReportType = Literal[
    "customer_analysis",      # 客户经营分析（周报/月报）
    "daily_report_summary",   # 员工日报汇总
    "weekly_report_summary",  # 员工周报汇总
    "psych_weekly",           # 学生心理健康周报
    "complaint_weekly",       # 投诉处理周报
]


class ReportGenerateRequest(BaseModel):
    """手动生成报告请求。周期缺省时使用数据提供器的参考周期。"""
    report_type: ReportType
    period_start: datetime | None = None
    period_end: datetime | None = None


class ReportOut(BaseModel):
    """报告列表 / 详情 / 生成返回。"""
    id: int
    report_type: str
    report_title: str | None = None
    report_content: dict | None = None
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None
    generated_by: int | None = None
    status: str
    version: int = 1
    data_source_status: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReportListOut(BaseModel):
    """报告列表条目（M5-12.3 瘦身：不回传完整 report_content，载荷从详情接口取）。"""
    id: int
    report_type: str
    report_title: str | None = None
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None
    generated_by: int | None = None
    status: str
    version: int = 1
    data_source_status: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
