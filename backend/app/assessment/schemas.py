from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SourceType = Literal["text", "dialogue", "registration", "file_text", "batch"]


class AssessmentRequest(BaseModel):
    """单条研判请求；文件解析由统一上传层完成后传入 ``content``。"""

    content: str = Field(..., min_length=1, description="原始文本或已解析的文件文本")
    source_type: SourceType = "text"
    registration: dict[str, Any] | None = Field(
        default=None,
        description="注册表单结构化字段；提供后只按字段取值，不自由猜测",
    )

    @model_validator(mode="after")
    def registration_requires_data(self) -> "AssessmentRequest":
        if self.source_type == "registration" and not self.registration:
            raise ValueError("注册信息渠道必须提供 registration 字段")
        return self


class BatchAssessmentRequest(BaseModel):
    records: list[AssessmentRequest] = Field(..., min_length=1, max_length=500)


class AssessmentRecord(BaseModel):
    """与研判提示词约定一致的可序列化结果。"""

    index: int
    status: Literal["valid", "invalid_input", "invalid_phone"]
    invalid_reason: str | None = None
    customer: dict[str, Any]
    conflicts: list[str] = Field(default_factory=list)
    assessments: dict[str, Any] | None = None
    recommended_projects: list[dict[str, str]] | None = None
    missing_info: list[str] = Field(default_factory=list)
    customer_overview: str | None = None
    follow_up_advice: str | None = None
