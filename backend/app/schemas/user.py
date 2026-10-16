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
    user_type: str = Field(..., pattern="^(STUDENT|EMPLOYEE)$", description="用户类型")
    contact_info: Optional[str] = Field(None, description="联系方式")


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
