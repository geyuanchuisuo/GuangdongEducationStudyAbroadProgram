"""一期种子数据脚本（幂等，可重复运行）。

运行方式（在 backend/ 目录下）：
    uv run python scripts/seed.py

会创建表并插入：测试员工/经理账号、示例课程、示例活动。
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.security import hash_password
from app.database import async_session_factory, engine
from app.models import Base
from app.models.course import CourseProject
from app.models.event import EventLecture
from app.models.user import User


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now()
    async with async_session_factory() as db:
        # 测试账号（幂等）
        if not (await db.execute(select(User).where(User.username == "employee01"))).scalar_one_or_none():
            db.add(User(username="employee01", password_hash=hash_password("123456"), real_name="测试员工", user_type="EMPLOYEE"))
        if not (await db.execute(select(User).where(User.username == "manager01"))).scalar_one_or_none():
            db.add(User(username="manager01", password_hash=hash_password("123456"), real_name="测试经理", user_type="MANAGER"))
        await db.commit()

        # 示例课程（幂等）
        if (await db.execute(select(func.count(CourseProject.id)))).scalar_one() == 0:
            db.add_all([
                CourseProject(
                    project_name="德国本科留学申请", category="留学申请",
                    description="面向高中/本科生的德国公立大学申请全流程服务。",
                    target_audience="高中及本科在读学生", tuition_fee=Decimal("30000.00"), duration="12个月",
                ),
                CourseProject(
                    project_name="德语A1-B2语言培训", category="语言培训",
                    description="德语零基础到B2的系统语言课程。",
                    target_audience="有留德意向的学员", tuition_fee=Decimal("15000.00"), duration="6个月",
                ),
                CourseProject(
                    project_name="背景提升科研项目", category="背景提升",
                    description="与高校导师合作的科研/竞赛背景提升项目。",
                    target_audience="本科在读学生", tuition_fee=Decimal("20000.00"), duration="3个月",
                ),
            ])
            await db.commit()
            print("课程种子数据已插入")

        # 示例活动（幂等）
        if (await db.execute(select(func.count(EventLecture.id)))).scalar_one() == 0:
            db.add_all([
                EventLecture(
                    event_name="德国留学线上分享会", event_type="线上",
                    start_time=now + timedelta(days=7), end_time=now + timedelta(days=7, hours=1),
                    location="腾讯会议", max_participants=100, description="留德政策与院校申请解读。",
                ),
                EventLecture(
                    event_name="招生官线下见面会", event_type="线下",
                    start_time=now + timedelta(days=14), end_time=now + timedelta(days=14, hours=2),
                    location="广州办公室", max_participants=50, description="与德国高校招生官面对面交流。",
                ),
            ])
            await db.commit()
            print("活动种子数据已插入")

    print("种子数据完成：")
    print("  员工账号 employee01 / 123456")
    print("  经理账号 manager01 / 123456")


if __name__ == "__main__":
    asyncio.run(seed())
