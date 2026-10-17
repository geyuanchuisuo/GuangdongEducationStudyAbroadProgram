from datetime import datetime

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    event_name: str
    event_type: str | None = None
    start_time: datetime
    end_time: datetime
    location: str | None = None
    max_participants: int
    current_participants: int
    description: str | None = None
    status: str
    create_time: datetime | None = None

    model_config = {"from_attributes": True}


class RegistrationOut(BaseModel):
    id: int
    event_id: int
    user_id: int
    status: str
    create_time: datetime | None = None

    model_config = {"from_attributes": True}
