from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CourseProject(Base):
    __tablename__ = "course_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    tuition_fee = mapped_column(Numeric(10, 2), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="上架", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())


class Policy(Base):
    """留学政策资讯（公开内容页数据源，v6.11.23 建表接库）。"""

    __tablename__ = "policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 德国/新加坡/综合
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    create_time = mapped_column(DateTime, server_default=func.now())
