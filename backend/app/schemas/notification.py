from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    """站内通知输出模型（对应接口契约 §8.2）"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    title: str | None = None
    content: str | None = None
    is_read: bool = False
    related_type: str | None = None
    related_id: int | None = None
    created_at: datetime | None = None
