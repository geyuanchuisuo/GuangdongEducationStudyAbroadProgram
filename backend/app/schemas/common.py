from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class PageResult(BaseModel, Generic[T]):
    total: int
    items: list[T]


class IdResponse(BaseModel):
    id: int


class StatusResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str
