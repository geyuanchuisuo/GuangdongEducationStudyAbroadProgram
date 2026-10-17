from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 日报 ──────────────────────────────────────────────
class DailyReportCreate(BaseModel):
    report_date: date = Field(..., description="日报日期")
    content: str = Field(..., min_length=1, description="日报内容（结构化文本）")


class DailyReportOut(BaseModel):
    id: int
    employee_id: int
    report_date: date
    content: str
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DailyReportSummaryItem(BaseModel):
    report_date: date
    submitted: int = 0


# ── 待办 ──────────────────────────────────────────────
class TodoCreate(BaseModel):
    todo_type: str = Field(..., max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    related_type: Optional[str] = Field(None, max_length=50)
    related_id: Optional[int] = None
    priority: str = Field("medium", max_length=10)
    due_time: Optional[datetime] = None


class TodoUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=20, description="pending/done/cancelled")
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=10)
    due_time: Optional[datetime] = None


class TodoOut(BaseModel):
    id: int
    employee_id: int
    todo_type: str
    title: str
    description: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    status: str
    priority: str
    due_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 组织架构 ──────────────────────────────────────────
class OrgNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    org_type: str
    leader_id: Optional[int] = None
    sort_order: int
    status: str
    children: list["OrgNode"] = []

    model_config = {"from_attributes": True}


OrgNode.model_rebuild()


# ── 成绩 ──────────────────────────────────────────────
class ScoreCreate(BaseModel):
    student_id: int = Field(..., description="学生 user id")
    course_name: str = Field(..., min_length=1, max_length=100)
    score: float = Field(..., ge=0, le=999.99)
    semester: Optional[str] = Field(None, max_length=50)


class ScoreOut(BaseModel):
    id: int
    student_id: int
    course_name: str
    score: float
    semester: Optional[str] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 代客申请留学生（走 approval convert） ─────────────
class ConvertApplyCreate(BaseModel):
    customer_id: int = Field(..., description="客户主表 ID")
    title: Optional[str] = Field(None, max_length=200, description="审批标题，缺省自动生成")
    approver_id: int = Field(..., description="经理 user id")


class ConvertApplyOut(BaseModel):
    approval_id: int
    biz_type: str
    biz_id: int
    status: str


# ── 学生行政服务审批（员工代处理/审批） ───────────────
class AdminServiceOut(BaseModel):
    id: int
    student_id: int
    service_type: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    status: str
    approver_id: Optional[int] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminServiceAction(BaseModel):
    action: str = Field(..., description="approve / reject")
    comment: Optional[str] = None


# ── 口述日报（AI 整理） ───────────────────────────────
class OralReportCreate(BaseModel):
    raw_text: str = Field(..., min_length=1, description="员工口述/随意记录原文")
    report_date: Optional[date] = Field(None, description="日报日期，缺省今天")


class OralReportOut(BaseModel):
    raw_text: str
    structured: str = Field(..., description="AI 整理后的结构化日报文本")
    report_date: date
    session_id: Optional[str] = None
    saved_report_id: Optional[int] = Field(None, description="如同时落库，返回日报 ID")


# ── CRM 客户录入（多格式：文字 + 已上传文件） ──────────
class CrmLeadCreate(BaseModel):
    """员工录入线索。

    多格式支持：
    - 纯文字：raw_text 必填
    - 文件（PDF/照片/Word/Excel）：先调 POST /api/v1/files/upload 拿 file_url，再传入 file_urls
    - 客户基础字段（phone/name/wechat 等）可选；若 phone 已有 customer，自动关联
    """
    raw_text: Optional[str] = Field(None, description="原始录入文本")
    file_urls: Optional[list[str]] = Field(None, description="已上传文件的 URL 列表")
    phone: Optional[str] = Field(None, max_length=20, description="手机号（有效性标准）")
    name: Optional[str] = Field(None, max_length=100)
    wechat: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    education: Optional[str] = Field(None, max_length=50)
    source_channel: Optional[str] = Field(None, max_length=32, description="来源渠道")
    background_info: Optional[str] = Field(None, description="背景信息")
    auto_assess: bool = Field(True, description="是否自动调 AI 研判")


class CrmLeadOut(BaseModel):
    lead_id: int
    customer_id: Optional[int] = None
    customer_existed: bool = Field(..., description="手机号是否已存在客户")
    assessment_id: Optional[int] = None
    status: str
    message: str


class CrmFollowUpCreate(BaseModel):
    customer_id: int
    follow_type: Optional[str] = Field(None, max_length=32)
    content: str = Field(..., min_length=1)
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None


class CrmFollowUpOut(BaseModel):
    id: int
    customer_id: int
    employee_id: int
    follow_type: Optional[str] = None
    content: Optional[str] = None
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 指令式业务处理（AI 解析 + 二次确认） ────────────────
class CommandParseCreate(BaseModel):
    """员工用自然语言下达业务指令，AI 解析为结构化动作，返回 token。"""
    text: str = Field(..., min_length=1, description="自然语言指令，例如：给客户张三发条跟进记录：明天约面谈")


class CommandParsedAction(BaseModel):
    """AI 解析出的待执行动作。"""
    action_type: str = Field(..., description="follow_up.create / todo.create / score.record 等")
    params: dict = Field(default_factory=dict)
    summary: str = Field(..., description="员工可读的动作描述，用于二次确认展示")


class CommandParseOut(BaseModel):
    token: str = Field(..., description="待确认令牌，10 分钟有效")
    action: CommandParsedAction
    expires_in: int = 600


class CommandExecuteCreate(BaseModel):
    token: str = Field(..., description="来自 parse 接口的待确认令牌")
    confirm: bool = Field(True, description="true=执行；false=取消")


class CommandExecuteOut(BaseModel):
    executed: bool
    result: Optional[dict] = None
    message: str
