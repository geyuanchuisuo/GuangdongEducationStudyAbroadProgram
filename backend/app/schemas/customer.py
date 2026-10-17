from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    wechat: Optional[str] = Field(None, max_length=100, description="微信号")
    name: Optional[str] = Field(None, max_length=100, description="姓名")
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")
    education: Optional[str] = Field(None, max_length=50, description="学历")
    source_channel: Optional[str] = Field(None, max_length=32, description="来源渠道")


class CustomerCreate(CustomerBase):
    phone: str = Field(..., max_length=20, description="手机号(必填)")
    name: str = Field(..., min_length=1, max_length=100, description="姓名(必填)")


class CustomerUpdate(BaseModel):
    phone: Optional[str] = Field(None, max_length=20)
    wechat: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    education: Optional[str] = Field(None, max_length=50)
    owner_employee_id: Optional[int] = None
    status: Optional[str] = Field(None, max_length=20)


class CustomerOut(CustomerBase):
    id: int
    owner_employee_id: Optional[int] = None
    status: str
    phone_status: str
    first_register_at: Optional[datetime] = None
    first_submit_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    auto_churned: bool
    sys_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LeadCreate(BaseModel):
    source: Optional[str] = Field(None, max_length=32, description="线索来源")
    raw_input: Optional[str] = Field(None, description="原始录入信息")
    background_info: Optional[str] = Field(None, description="背景信息")
    customer_id: Optional[int] = Field(None, description="关联客户ID")


class LeadOut(BaseModel):
    id: int
    customer_id: Optional[int] = None
    source: Optional[str] = None
    raw_input: Optional[str] = None
    background_info: Optional[str] = None
    status: str
    owner_employee_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AssessmentOut(BaseModel):
    id: int
    customer_id: Optional[int] = None
    batch_no: Optional[str] = None
    status: str
    sg_conclusion: Optional[str] = None
    de_conclusion: Optional[str] = None
    score: Optional[int] = None
    overview: Optional[str] = None
    follow_up_advice: Optional[str] = None
    prompt_version: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FollowUpCreate(BaseModel):
    follow_type: Optional[str] = Field(None, max_length=32)
    content: str = Field(..., min_length=1)
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None


class FollowUpOut(BaseModel):
    id: int
    customer_id: int
    employee_id: int
    follow_type: Optional[str] = None
    content: Optional[str] = None
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
