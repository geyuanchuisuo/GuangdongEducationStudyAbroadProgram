from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrmLeadCreate(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20, description="手机号(业务唯一键，落在 customer 表)")
    wechat: str | None = Field(None, max_length=100, description="微信号")
    name: str | None = None
    gender: str | None = None
    age: int | None = None
    education: str | None = None
    economy: str | None = None
    needs: str | None = None
    study_intent: str | None = None
    german_ability: str | None = None
    english_ability: str | None = None
    closed_training: str | None = None
    criminal_record: str | None = None
    belt_and_road: str | None = None
    source: str | None = Field(None, max_length=32, description="线索来源")
    raw_input: str | None = None
    background_info: str | None = None
    owner_employee_id: int | None = None


class CrmLeadUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    age: int | None = None
    education: str | None = None
    economy: str | None = None
    needs: str | None = None
    study_intent: str | None = None
    german_ability: str | None = None
    english_ability: str | None = None
    closed_training: str | None = None
    criminal_record: str | None = None
    belt_and_road: str | None = None
    source: str | None = None
    raw_input: str | None = None
    background_info: str | None = None
    owner_employee_id: int | None = None


class CrmLeadOut(BaseModel):
    id: int
    customer_id: int | None = None
    source: str | None = None
    raw_input: str | None = None
    background_info: str | None = None
    status: str
    owner_employee_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LeadStatusChange(BaseModel):
    status: str = Field(..., description="目标状态")


class LeadFollowUp(BaseModel):
    content: str = Field(..., min_length=1)
    follow_type: str | None = None
    next_action: str | None = None
    next_date: datetime | None = None


class FollowUpOut(BaseModel):
    id: int
    customer_id: int
    employee_id: int
    follow_type: str | None = None
    content: str | None = None
    next_action: str | None = None
    next_date: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssessmentCreate(BaseModel):
    customer_id: int | None = None
    batch_no: str | None = None
    input_source: str | None = None
    status: str | None = None
    sg_conclusion: str | None = None
    de_conclusion: str | None = None
    dimensions_json: Any = None
    matched_programs_json: Any = None
    recommended_json: Any = None
    missing_info_json: Any = None
    conflicts_json: Any = None
    overview: str | None = None
    follow_up_advice: str | None = None
    score: int | None = None
    prompt_version: str | None = None
    employee_id: int | None = None


class AssessmentOut(BaseModel):
    id: int
    customer_id: int | None = None
    batch_no: str | None = None
    input_source: str | None = None
    status: str
    sg_conclusion: str | None = None
    de_conclusion: str | None = None
    dimensions_json: Any = None
    matched_programs_json: Any = None
    recommended_json: Any = None
    missing_info_json: Any = None
    conflicts_json: Any = None
    overview: str | None = None
    follow_up_advice: str | None = None
    score: int | None = None
    prompt_version: str | None = None
    dify_run_id: str | None = None
    employee_id: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
