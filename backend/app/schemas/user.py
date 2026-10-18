from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    real_name: str = Field(..., min_length=2, max_length=50, description="真实姓名")
    user_type: str = Field(..., pattern="^(STUDENT|EMPLOYEE|PROSPECT)$", description="用户类型")
    contact_info: Optional[str] = Field(None, description="联系方式")
    # v6.9.11/v6.9.13：PROSPECT 注册选填画像字段（落 customer 主表，均与列一致可空）
    phone: Optional[str] = Field(None, max_length=20, description="手机号（客户业务唯一键，PROSPECT 注册建议填写）")
    wechat: Optional[str] = Field(None, max_length=100, description="微信号（PROSPECT 选填）")
    age: Optional[int] = Field(None, ge=1, le=120, description="年龄（PROSPECT 选填）")
    education: Optional[str] = Field(None, max_length=50, description="学历（PROSPECT 选填）")


class LoginResponse(BaseModel):
    access_token: str
    user_id: int
    username: str
    real_name: str
    user_type: str


class UserOut(BaseModel):
    id: int
    username: str
    real_name: str
    user_type: str
    employee_role: Optional[str] = None
    department: Optional[str] = None
    contact_info: Optional[str] = None
    status: str
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    real_name: Optional[str] = Field(None, min_length=2, max_length=50)
    contact_info: Optional[str] = None
    department: Optional[str] = None
