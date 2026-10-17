import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base
from app.models.customer import Customer, PendingLead
from app.models.customer_service import CsChatMessage, CsIntentLog, CsRecommendLog
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.ai_service import AiService
from app.services.crm_service import CrmService
from app.services.event_bus import event_bus


class FakeDify:
    """假 Dify 客户端：按预设 answer 返回，不发起真实 HTTP 请求。"""

    def __init__(self, answer: str):
        self._answer = answer

    async def chat(self, query, user, conversation_id=None):
        return {"answer": self._answer, "conversation_id": "dify-conv-1"}


@pytest_asyncio.fixture
async def cs_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DIFY_CUSTOMER_AGENT_KEY", "test-key")

    async def _noop_publish(*args, **kwargs):
        return 0

    monkeypatch.setattr(event_bus, "publish", _noop_publish)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cs.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        cs_repo = CustomerServiceRepository(session)
        crm_service = CrmService(CrmRepository(session), CustomerRepository(session))
        yield session, cs_repo, crm_service

    await engine.dispose()


async def test_intent_and_recommendation(cs_env):
    """阶段1 意图落库 + 阶段4 推荐进 card_data。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify('[intent:program_consult] 推荐如下 [RECOMMEND][{"project": "新加坡本科"}]'),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="你好"))
    assert resp.intent == "program_consult"
    assert resp.recommendations == [{"project": "新加坡本科"}]
    assert resp.answer == "推荐如下"

    logs = (await session.execute(select(CsIntentLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].intent_type == "program_consult"
    assert logs[0].converted is False

    msgs = (await session.execute(select(CsChatMessage).where(CsChatMessage.role == "assistant"))).scalars().all()
    assert len(msgs) == 1
    assert msgs[0].card_data == {"recommendations": [{"project": "新加坡本科"}]}


async def test_multi_turn_limit(cs_env):
    """阶段2 多轮上限：超过 MAX_TURNS 归档旧会话并开新会话。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(cs_repo, dify=FakeDify("好的"), crm_service=crm_service)

    first = await svc.chat(ChatRequest(message="1"))
    sid_a = int(first.conversation_id)
    for i in range(9):
        r = await svc.chat(ChatRequest(message=str(i), conversation_id=str(sid_a)))
        assert int(r.conversation_id) == sid_a

    r11 = await svc.chat(ChatRequest(message="11", conversation_id=str(sid_a)))
    sid_b = int(r11.conversation_id)
    assert sid_b != sid_a

    old = await cs_repo.get_session(sid_a)
    assert old.status == "archived"


async def test_lead_conversion(cs_env):
    """阶段3 高意向转线索：提取手机号建档，回填 session.customer_id 且意图日志 converted=True。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify("[intent:lead_capture] 收到，顾问稍后联系您"),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="我叫王五，电话13812345678"))
    sid = int(resp.conversation_id)

    sess = await cs_repo.get_session(sid)
    assert sess.customer_id is not None

    customer = (await session.execute(select(Customer).where(Customer.id == sess.customer_id))).scalar_one()
    assert customer.phone == "13812345678"
    assert customer.source_channel == "客服"

    logs = (await session.execute(select(CsIntentLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].converted is True
    assert logs[0].customer_id == customer.id


async def test_recommendation_log(cs_env):
    """阶段4 推荐落库：[RECOMMEND] 解析后写 cs_recommend_log（含类型/名称）。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify('[intent:course_recommend] 给你推荐 [RECOMMEND][{"id": 3, "type": "course", "name": "新加坡本科班"}, {"name": "招生见面会"}]'),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="有什么适合我的课程吗"))
    assert len(resp.recommendations) == 2

    logs = (await session.execute(select(CsRecommendLog))).scalars().all()
    assert len(logs) == 2
    assert logs[0].course_id == 3
    assert logs[0].event_id is None
    assert logs[0].recommendation_type == "course"
    assert logs[0].item_name == "新加坡本科班"
    assert logs[1].recommendation_type == "other"
    assert logs[1].item_name == "招生见面会"


async def test_slots_profile_in_lead(cs_env):
    """信息采集：建档携带 [SLOTS] 画像字段（含 age「17岁」清洗）。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify('[intent:lead_capture] 收到 [SLOTS]{"name": "王五", "gender": "男", "age": "17岁", "education": "高中", "needs": "升学"}'),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="我叫王五，电话13812345678，高二"))
    sid = int(resp.conversation_id)

    sess = await cs_repo.get_session(sid)
    customer = (await session.execute(select(Customer).where(Customer.id == sess.customer_id))).scalar_one()
    assert customer.name == "王五"
    assert customer.gender == "男"
    assert customer.age == 17
    assert customer.education == "高中"
    assert customer.needs == "升学"

    msgs = (await session.execute(select(CsChatMessage).where(CsChatMessage.role == "assistant"))).scalars().all()
    assert msgs[0].slots_json["name"] == "王五"
    assert msgs[0].content.endswith("收到")


async def test_wechat_pending_lead(cs_env):
    """仅微信号无手机号 → pending_lead 待补全线索（同号去重，converted=True）。"""
    session, cs_repo, crm_service = cs_env
    customer_repo = CustomerRepository(session)
    svc = AiService(cs_repo, dify=FakeDify("[intent:lead_capture] 好的"), crm_service=crm_service, customer_repo=customer_repo)

    resp = await svc.chat(ChatRequest(message="我微信 wx_wangwu01，加我详聊"))
    sid = int(resp.conversation_id)

    pendings = (await session.execute(select(PendingLead))).scalars().all()
    assert len(pendings) == 1
    assert pendings[0].wechat == "wx_wangwu01"
    assert pendings[0].source_session_id == sid
    # 手机号列 customers 表不应建档
    assert (await session.execute(select(Customer))).scalars().all() == []

    # 同一微信号再次沟通 → 不重复建档
    await svc.chat(ChatRequest(message="再补充下：微信号 wx_wangwu01", conversation_id=str(sid)))
    pendings = (await session.execute(select(PendingLead))).scalars().all()
    assert len(pendings) == 1


async def test_slots_update_existing_customer(cs_env):
    """信息更新：已关联客户的会话补充槽位 → 更新画像字段而非重复建档。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify("[intent:lead_capture] 收到"),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="电话13812345678"))
    sid = int(resp.conversation_id)

    svc2 = AiService(
        cs_repo,
        dify=FakeDify('[intent:chitchat] 好 [SLOTS]{"name": "王六", "german_ability": "A2"}'),
        crm_service=crm_service,
        customer_repo=CustomerRepository(session),
    )
    await svc2.chat(ChatRequest(message="我叫王六，德语A2", conversation_id=str(sid)))

    sess = await cs_repo.get_session(sid)
    customers = (await session.execute(select(Customer))).scalars().all()
    assert len(customers) == 1  # 未重复建档
    assert customers[0].id == sess.customer_id
    assert customers[0].name == "王六"
    assert customers[0].german_ability == "A2"
