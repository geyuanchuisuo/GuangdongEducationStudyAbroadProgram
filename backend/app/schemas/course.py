from datetime import datetime
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
