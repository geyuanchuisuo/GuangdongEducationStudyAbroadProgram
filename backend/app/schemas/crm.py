from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrmLeadCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20, description="电话号码（唯一有效性/去重标准）")
    contact_info: str | None = None
    background_info: str | None = None
    source: str | None = Field(None, max_length=20)
    profile: dict[str, Any] | None = None
    owner_employee_id: int | None = None


class CrmLeadUpdate(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, min_length=5, max_length=20)
    contact_info: str | None = None
    background_info: str | None = None
    source: str | None = None
    profile: dict[str, Any] | None = None
    owner_employee_id: int | None = None


class CrmLeadOut(BaseModel):
    id: int
    customer_name: str
    phone: str | None = None
    contact_info: str | None = None
    background_info: str | None = None
    source: str | None = None
    profile: Any = None
    follow_up_history: Any = None
    status: str
    owner_employee_id: int
    create_time: datetime | None = None
    update_time: datetime | None = None

    model_config = {"from_attributes": True}


class LeadStatusChange(BaseModel):
    status: str = Field(..., description="目标状态")


class LeadFollowUp(BaseModel):
    content: str = Field(..., min_length=1)
    follow_up_type: str | None = None
    remark: str | None = None


class AssessmentCreate(BaseModel):
    customer_name: str | None = None
    source_type: str | None = None
    source_file: str | None = None
    extracted_info: dict[str, Any] | None = None
    assessment_result: dict[str, Any] | None = None
    match_score: int | None = None
    matched_products: Any = None
    recommendation: str | None = None
    status: str | None = None
    employee_id: int | None = None
    is_valid: bool | None = True
    invalid_reason: str | None = None


class AssessmentOut(BaseModel):
    id: int
    customer_name: str | None = None
    source_type: str | None = None
    source_file: str | None = None
    phone: str | None = None
    lead_id: int | None = None
    extracted_info: Any = None
    assessment_result: Any = None
    match_score: int | None = None
    matched_products: Any = None
    recommendation: str | None = None
    status: str
    employee_id: int | None = None
    is_valid: bool | None = None
    invalid_reason: str | None = None
    create_time: datetime | None = None

    model_config = {"from_attributes": True}
