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
