from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel
class CourseOut(BaseModel):
    id: int
    project_name: str
    category: str | None = None
    description: str | None = None
    target_audience: str | None = None
    tuition_fee: Decimal | None = None
    duration: str | None = None
    status: str
    create_time: datetime | None = None

    model_config = {"from_attributes": True}


class PolicyOut(BaseModel):
    """留学政策资讯（v6.11.23 建表接库）。"""

    id: int
    title: str
    country: str
    category: str | None = None
    summary: str
    content: str | None = None
    publish_date: date | None = None
    status: str = "published"

    model_config = {"from_attributes": True}
