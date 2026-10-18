from datetime import datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.course import CourseProject
from app.models.event import EventLecture
from app.models.user import User

# e2e_m3m4_test.py 是 Docker 容器内直接执行的脚本（import 时替换 sys.stdout），
# 不应被 pytest 收集（默认 *_test.py 模式会 import 它，破坏捕获导致全套收集失败）
collect_ignore = ["e2e_m3m4_test.py", "e2e_convert_test.py"]


@pytest_asyncio.fixture
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now()
    async with session_factory() as session:
        session.add_all([
            User(username="employee01", password_hash=hash_password("123456"), real_name="员工一", user_type="EMPLOYEE"),
            User(username="employee02", password_hash=hash_password("123456"), real_name="员工二", user_type="EMPLOYEE"),
            User(username="manager01", password_hash=hash_password("123456"), real_name="经理一", user_type="MANAGER"),
            CourseProject(project_name="德国本科留学申请", category="留学申请", status="上架"),
            CourseProject(project_name="德语A1-B2语言培训", category="语言培训", status="上架"),
            EventLecture(
                event_name="线上分享会", event_type="线上",
                start_time=now + timedelta(days=7), end_time=now + timedelta(days=7, hours=1),
                max_participants=100, status="报名中",
            ),
            EventLecture(
                event_name="满员活动", event_type="线上",
                start_time=now + timedelta(days=14), end_time=now + timedelta(days=14, hours=1),
                max_participants=1, status="报名中",
            ),
        ])
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def login(client):
    async def _login(username: str, password: str = "123456") -> dict:
        resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert resp.json()["code"] == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

    return _login
