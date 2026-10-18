import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models import Base
from app.models.customer_service import CsChatMessage, CsChatSession, CsFaq


@pytest_asyncio.fixture
async def cs_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cs_public.db'}")
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


async def test_faq_list_empty_and_filtered(cs_client):
    """/cs/faq：空表可查；仅返回启用项，支持分类/关键词。"""
    client, factory = cs_client
    resp = await client.get("/api/v1/cs/faq")
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["total"] == 0

    async with factory() as session:
        session.add_all(
            [
                CsFaq(category="课程", question="有哪些课程？", answer="有德国双元制和新加坡本硕。", sort_order=1),
                CsFaq(category="费用", question="学费多少？", answer="视项目而定。", sort_order=2),
                CsFaq(category="费用", question="隐藏问题", answer="不可见", enabled=False, sort_order=3),
            ]
        )
        await session.commit()

    resp = await client.get("/api/v1/cs/faq")
    assert resp.json()["data"]["total"] == 2

    resp = await client.get("/api/v1/cs/faq", params={"keyword": "课程"})
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["question"] == "有哪些课程？"

    resp = await client.get("/api/v1/cs/faq", params={"category": "费用"})
    assert resp.json()["data"]["total"] == 1


async def test_session_messages(cs_client):
    """/cs/sessions/{id}/messages：按序返回消息；不存在返回 40401。"""
    client, factory = cs_client
    resp = await client.get("/api/v1/cs/sessions/999/messages")
    assert resp.json()["code"] == 40401

    async with factory() as session:
        s = CsChatSession()
        session.add(s)
        await session.flush()
        session.add(CsChatMessage(session_id=s.id, role="user", content="你好"))
        session.add(
            CsChatMessage(
                session_id=s.id,
                role="assistant",
                content="推荐给你",
                intent="course_recommend",
                card_data={"recommendations": [{"id": 1, "type": "course", "name": "德国双元制"}]},
            )
        )
        await session.commit()
        sid = s.id

    resp = await client.get(f"/api/v1/cs/sessions/{sid}/messages")
    body = resp.json()
    assert body["code"] == 200
    assert [m["role"] for m in body["data"]] == ["user", "assistant"]
    assert body["data"][1]["intent"] == "course_recommend"
    assert body["data"][1]["card_data"]["recommendations"][0]["name"] == "德国双元制"
