"""研判结果显式落库的请求契约。

研判引擎（``app.assessment``）只返回结果、不落库；本模块定义 CRM 侧显式保存
研判记录时使用的请求体，复用引擎的 ``AssessmentRecord`` 与 5 值 ``SourceType``。
"""

from pydantic import BaseModel

from app.assessment.schemas import AssessmentRecord, SourceType


class AssessmentSaveRequest(BaseModel):
    """携带引擎返回的研判记录 + 来源信息，供 CRM 侧显式保存。"""

    record: AssessmentRecord
    source_type: SourceType = "text"
    source_file: str | None = None
