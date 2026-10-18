"""意图码归一（normalize_intent，v6.10.6）：Dify 分支码 / seed 遗留码 → 契约 9 码。

覆盖：映射表、契约码透传、未知码原样保留、写库归一（cs_intent_log）、
留资归位（converted → lead_capture）。
"""
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base
from app.models.customer_service import CsIntentLog
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.cs_agent_service import AiService

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

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'intent.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        cs_repo = CustomerServiceRepository(session)
        crm_service = CrmService(CrmRepository(session), CustomerRepository(session))
        yield session, cs_repo, crm_service

    await engine.dispose()


def test_normalize_intent_aliases():
    """Dify 分支码 / seed 遗留码 → 契约码。"""
    ni = AiService.normalize_intent
    assert ni("business") == "program_consult"
    assert ni("policy") == "policy_qa"
    assert ni("event_signup") == "event_query"
    assert ni("general_chat") == "chitchat"
    assert ni("course_inquiry") == "program_consult"
    assert ni("price_consult") == "program_consult"
    assert ni("study_abroad_consult") == "program_consult"
    assert ni("event_registration") == "event_query"


def test_normalize_intent_passthrough():
    """契约码透传、未知码原样保留（不吞数据）、空值透传。"""
    ni = AiService.normalize_intent
    for code in ("program_consult", "course_recommend", "policy_qa", "company_info", "event_query", "faq", "chitchat", "lead_capture", "transfer_human"):
        assert ni(code) == code
    assert ni("xyz_policy") == "xyz_policy"
    assert ni("") == ""
    assert ni(None) is None


async def test_chat_normalizes_dify_branch_codes(cs_env):
    """VM 分支码 [intent:policy]/[intent:event_signup] 写库即归一为契约码。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(cs_repo, dify=FakeDify("[intent:policy] 德国双元制是…"), crm_service=crm_service)
    resp = await svc.chat(ChatRequest(message="德国留学政策是什么"))
    assert resp.intent == "policy_qa"

    svc2 = AiService(cs_repo, dify=FakeDify("[intent:event_signup] 活动详情…"), crm_service=crm_service)
    resp2 = await svc2.chat(ChatRequest(message="有什么讲座"))
    assert resp2.intent == "event_query"

    logs = (await session.execute(select(CsIntentLog))).scalars().all()
    assert [log.intent_type for log in logs] == ["policy_qa", "event_query"]


async def test_chat_preserves_unknown_intent(cs_env):
    """未识别码原样落库（不吞数据），便于后续发现新漂移。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(cs_repo, dify=FakeDify("[intent:xyz_policy] 好的"), crm_service=crm_service)
    resp = await svc.chat(ChatRequest(message="你好"))

    assert resp.intent == "xyz_policy"
    logs = (await session.execute(select(CsIntentLog))).scalars().all()
    assert logs[0].intent_type == "xyz_policy"


async def test_lead_conversion_normalizes_to_lead_capture(cs_env):
    """转线索成功（converted=True）→ intent 归位为契约码 lead_capture。"""
    session, cs_repo, crm_service = cs_env
    svc = AiService(
        cs_repo,
        dify=FakeDify("[intent:company_info] 收到，顾问稍后联系您"),
        crm_service=crm_service,
    )
    resp = await svc.chat(ChatRequest(message="我电话13812345678，想咨询下"))

    assert resp.intent == "lead_capture"
    logs = (await session.execute(select(CsIntentLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].intent_type == "lead_capture"
    assert logs[0].converted is True
