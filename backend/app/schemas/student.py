"""M4 学生模块 Schemas（v6.8.0）"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── 行政服务 ──
class AdminServiceCreate(BaseModel):
    service_type: str = Field(..., max_length=50, description="服务类型：请假/证明开具等")
    start_time: datetime | None = None
    end_time: datetime | None = None
    reason: str | None = Field(None, max_length=1000)
    related_academic_id: int | None = None


class AdminServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_type: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    reason: str | None = None
    status: str
    approver_id: int | None = None
    related_academic_id: int | None = None
    create_time: datetime


# ── 心理关怀 ──
class PsychChatCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None, max_length=64, description="会话ID，传 new 开新会话")


class PsychChatOut(BaseModel):
    reply: str
    session_id: str
    emotion_tag: str
    emotion_score: int
    alert_created: bool = False
    degraded: bool = False


class PsychProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    latest_emotion_tag: str | None = None
    emotion_score: int | None = None
    last_interaction_time: datetime | None = None
    emotion_history: list | None = None
    update_time: datetime | None = None


# ── 售后反馈 ──
class TicketCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    detail: str | None = Field(None, max_length=5000)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    detail: str | None = None
    status: str
    solution: str | None = None
    is_notified: bool
    create_time: datetime
    update_time: datetime


# ── 学业考务 ──
class AcademicItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_type: str
    title: str
    description: str | None = None
    course_name: str | None = None
    due_time: datetime
    reminder_sent: bool


class ScoreItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_name: str
    score: float
    semester: str | None = None
    create_time: datetime


class AcademicOut(BaseModel):
    academic_items: list[AcademicItemOut]
    scores: list[ScoreItemOut]
    score_summary: dict[str, Any]


# ── 进度追踪 ──
class ProgressStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: str
    status: str
    update_time: datetime
    notes: str | None = None


class ProgressUpdate(BaseModel):
    stage: str = Field(..., max_length=50)
    status: str = Field(..., max_length=50)
    notes: str | None = Field(None, max_length=2000)


# ── 生活支持 FAQ ──
class FaqItem(BaseModel):
    question: str
    answer: str


class LifeFaqOut(BaseModel):
    items: list[FaqItem]


# ── 更多服务 ──
class ServiceItem(BaseModel):
    code: str
    name: str
    description: str


class MoreServicesOut(BaseModel):
    items: list[ServiceItem]
