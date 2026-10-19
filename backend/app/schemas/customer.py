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
    economy: Optional[str] = Field(None, max_length=100, description="家庭经济状况")
    needs: Optional[str] = Field(None, max_length=200, description="职业/教育需求")
    study_intent: Optional[str] = Field(None, max_length=200, description="留学意愿及意向国家")
    german_ability: Optional[str] = Field(None, max_length=100, description="德语能力")
    english_ability: Optional[str] = Field(None, max_length=100, description="英语能力")
    closed_training: Optional[str] = Field(None, max_length=100, description="是否接受封闭式实训")
    criminal_record: Optional[str] = Field(None, max_length=100, description="有无犯罪记录")
    belt_and_road: Optional[str] = Field(None, max_length=200, description="一带一路/政策认知")
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
    economy: Optional[str] = Field(None, max_length=100)
    needs: Optional[str] = Field(None, max_length=200)
    study_intent: Optional[str] = Field(None, max_length=200)
    german_ability: Optional[str] = Field(None, max_length=100)
    english_ability: Optional[str] = Field(None, max_length=100)
    closed_training: Optional[str] = Field(None, max_length=100)
    criminal_record: Optional[str] = Field(None, max_length=100)
    belt_and_road: Optional[str] = Field(None, max_length=200)
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
    churned_at: Optional[datetime] = None
    reflowed_at: Optional[datetime] = None
    sys_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MyCustomerOut(CustomerOut):
    """本人客户档案（v6.11.19）：CustomerOut + 转化申请状态"""

    convert_status: str = Field("none", description="转化申请状态(none/pending/approved/rejected/cancelled)")


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


class CustomerStatusChange(BaseModel):
    status: str = Field(..., max_length=20, description="目标状态（英文或中文 6 态）")


class PendingLeadCreate(BaseModel):
    wechat: Optional[str] = Field(None, max_length=100, description="微信号")
    name: Optional[str] = Field(None, max_length=100, description="姓名")
    raw_info: Optional[str] = Field(None, description="原始信息")
    source_session_id: Optional[int] = Field(None, description="来源客服会话ID")


class PendingLeadOut(BaseModel):
    id: int
    wechat: Optional[str] = None
    name: Optional[str] = None
    raw_info: Optional[str] = None
    source_session_id: Optional[int] = None
    merged_customer_id: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PendingLeadMerge(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20, description="手机号(必填，业务唯一键)")
    name: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    education: Optional[str] = Field(None, max_length=50)
