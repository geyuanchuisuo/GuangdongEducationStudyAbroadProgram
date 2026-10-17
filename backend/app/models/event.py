from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventLecture(Base):
    __tablename__ = "event_lecture"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    start_time = mapped_column(DateTime, nullable=False, index=True)
    end_time = mapped_column(DateTime, nullable=False)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    max_participants: Mapped[int] = mapped_column(Integer, default=0)
    current_participants: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="报名中", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class EventRegistration(Base):
    __tablename__ = "event_registration"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_lecture.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="已报名")
    create_time = mapped_column(DateTime, server_default=func.now())
