from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApprovalCreate(BaseModel):
    biz_type: str = Field(..., description="业务类型(leave/convert/late_report/complaint)")
    biz_id: Optional[int] = Field(None, description="关联业务ID")
    title: Optional[str] = Field(None, max_length=200, description="审批标题")
    approver_id: int = Field(..., description="审批人ID")


class ApprovalAction(BaseModel):
    comment: Optional[str] = Field(None, description="审批意见")


class ApprovalTaskOut(BaseModel):
    id: int
    instance_id: int
    approver_id: int
    seq_no: int
    action: Optional[str] = None
    comment: Optional[str] = None
    acted_at: Optional[datetime] = None
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApprovalInstanceOut(BaseModel):
    id: int
    biz_type: str
    biz_id: Optional[int] = None
    title: Optional[str] = None
    initiator_id: int
    status: str
    current_step: int
    total_steps: int
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tasks: list[ApprovalTaskOut] = []

    model_config = {"from_attributes": True}


class BatchApprovalRequest(BaseModel):
    instance_ids: list[int] = Field(..., min_length=1, description="审批实例ID列表")
    comment: Optional[str] = Field(None, description="审批意见")
