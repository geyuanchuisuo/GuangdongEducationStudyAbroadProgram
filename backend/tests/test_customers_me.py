"""v6.11.19：GET /customers/me（本人客户档案 + 转化申请状态）API 级单测。

覆盖：本人查询（无申请→none）、未关联客户→40401、convert_status 取最新一条、
未登录→40101、越权防护（按 sys_user_id 强制反查，他人 customer 不可见）。
"""
from datetime import datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.customer import Customer
from app.models.system import ApprovalInstance
from app.models.user import User


@pytest_asyncio.fixture
async def me_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'customers_me.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client, username: str, password: str = "123456") -> dict:
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.json()["code"] == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def _make_user_with_customer(factory, username: str, user_type: str = "PROSPECT") -> tuple[int, int]:
    """建用户 + 关联 customer，返回 (user_id, customer_id)。"""
    async with factory() as session:
        user = User(username=username, password_hash=hash_password("123456"), real_name="测试客户", user_type=user_type, status="正常")
        session.add(user)
        await session.flush()
        customer = Customer(phone=f"139{user.id:08d}"[:11], name="测试客户", status="NEW", phone_status="normal", sys_user_id=user.id)
        session.add(customer)
        await session.commit()
        return user.id, customer.id


async def test_my_customer_ok_none_convert_status(me_client):
    """PROSPECT 本人查询：无 convert 申请时 convert_status=none，返回档案关键字段。"""
    client, factory = me_client
    _, cid = await _make_user_with_customer(factory, "13900000001")
    headers = await _login(client, "13900000001")

    resp = await client.get("/api/v1/customers/me", headers=headers)
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["id"] == cid
    assert body["data"]["name"] == "测试客户"
    assert body["data"]["status"] == "NEW"
    assert body["data"]["convert_status"] == "none"


async def test_my_customer_40401_when_no_customer(me_client):
    """已登录但无关联客户档案（如纯 STUDENT）返回 40401。"""
    client, factory = me_client
    async with factory() as session:
        session.add(User(username="stu01", password_hash=hash_password("123456"), real_name="纯学生", user_type="STUDENT", status="正常"))
        await session.commit()
    headers = await _login(client, "stu01")

    resp = await client.get("/api/v1/customers/me", headers=headers)
    assert resp.json()["code"] == 40401, resp.text


async def test_my_customer_convert_status_pending(me_client):
    """存在 pending 转化申请时 convert_status=pending。"""
    client, factory = me_client
    uid, cid = await _make_user_with_customer(factory, "13900000002")
    async with factory() as session:
        session.add(ApprovalInstance(id=1, biz_type="convert", biz_id=cid, title="代客申请", initiator_id=uid, status="pending"))
        await session.commit()
    headers = await _login(client, "13900000002")

    resp = await client.get("/api/v1/customers/me", headers=headers)
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["convert_status"] == "pending"


async def test_my_customer_convert_status_latest_wins(me_client):
    """多条 convert 申请取最新一条（approved 覆盖更早的 rejected）。"""
    client, factory = me_client
    uid, cid = await _make_user_with_customer(factory, "13900000003")
    now = datetime.now()
    async with factory() as session:
        session.add(ApprovalInstance(id=2, biz_type="convert", biz_id=cid, title="首次申请", initiator_id=uid, status="rejected", created_at=now - timedelta(days=2)))
        session.add(ApprovalInstance(id=3, biz_type="convert", biz_id=cid, title="二次申请", initiator_id=uid, status="approved", created_at=now - timedelta(days=1)))
        # 干扰项：其他 biz_type / 其他客户的 convert 申请不应被命中
        session.add(ApprovalInstance(id=4, biz_type="leave", biz_id=cid, title="请假", initiator_id=uid, status="pending", created_at=now))
        session.add(ApprovalInstance(id=5, biz_type="convert", biz_id=999999, title="他人申请", initiator_id=uid, status="pending", created_at=now))
        await session.commit()
    headers = await _login(client, "13900000003")

    resp = await client.get("/api/v1/customers/me", headers=headers)
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["convert_status"] == "approved"


async def test_my_customer_requires_login(me_client):
    """未登录访问返回 40101。"""
    client, _ = me_client
    resp = await client.get("/api/v1/customers/me")
    assert resp.json()["code"] == 40101, resp.text


async def test_my_customer_isolation(me_client):
    """越权防护：按 sys_user_id 强制反查，无法读取他人 customer。"""
    client, factory = me_client
    _, cid_a = await _make_user_with_customer(factory, "13900000004")
    _, cid_b = await _make_user_with_customer(factory, "13900000005")
    assert cid_a != cid_b
    headers = await _login(client, "13900000005")

    resp = await client.get("/api/v1/customers/me", headers=headers)
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["id"] == cid_b  # 只能拿到本人的，拿不到 cid_a
