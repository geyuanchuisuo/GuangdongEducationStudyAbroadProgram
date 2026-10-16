from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentAdminService(Base):
    __tablename__ = "student_admin_service"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_time = mapped_column(DateTime, nullable=True)
    end_time = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="待审批", index=True)
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
    related_academic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class StudentPsychProfile(Base):
    __tablename__ = "student_psych_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, unique=True, index=True)
    latest_emotion_tag: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    emotion_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_interaction_time = mapped_column(DateTime, nullable=True)
    emotion_history = mapped_column(JSON, nullable=True)
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class StudentPsychAlert(Base):
    __tablename__ = "student_psych_alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="未处理", index=True)
    teacher_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class StudentFeedbackTicket(Base):
    __tablename__ = "student_feedback_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="待处理", index=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time = mapped_column(DateTime, server_default=func.now())
    update_time = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class StudentScore(Base):
    __tablename__ = "student_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class StudentAcademic(Base):
    __tablename__ = "student_academic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_time = mapped_column(DateTime, nullable=False, index=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_time = mapped_column(DateTime, nullable=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class StudentApplicationProgress(Base):
    __tablename__ = "student_application_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    update_time = mapped_column(DateTime, server_default=func.now(), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True)
