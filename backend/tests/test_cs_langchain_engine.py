"""客服 LangChain 引擎测试（add_langchain 分支）。

覆盖：format_as_markers 组装、意图分类链回退、人设模板注入、
cs_agent_service CS_ENGINE 开关分流（dify 默认 / langchain 分支）。
"""
import asyncio
import tempfile

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.cs_agent_service import AiService
from app.services.cs_langchain.prompts import build_persona_message
from app.services.cs_langchain.schemas import CONTRACT_INTENTS, format_as_markers
from app.services.crm_service import CrmService
from app.services.event_bus import event_bus


# ── format_as_markers ──────────────────────────────────────────────────

def test_format_as_markers_with_slots():
    """正常槽位组装：intent + [SLOTS] JSON。"""
    markers = format_as_markers("program_consult", {"name": "王五", "study_intent": "新加坡"})
    assert markers == '[intent:program_consult][SLOTS]{"name": "王五", "study_intent": "新加坡"}'


def test_format_as_markers_empty_slots_omits_marker():
    """空槽位不输出 [SLOTS]。"""
    markers = format_as_markers("chitchat", {})
    assert markers == "[intent:chitchat]"
    assert "[SLOTS]" not in markers


def test_format_as_markers_unknown_intent_fallback_chitchat():
    """未识别意图回退 chitchat（保底不吞意图）。"""
    markers = format_as_markers("xyz_unknown", {"name": "张三"})
    assert markers.startswith("[intent:chitchat]")
    assert "[SLOTS]" in markers


def test_contract_intents_complete():
    """契约 9 码与 cs_agent_service.CONTRACT_INTENTS 一致。"""
    assert set(CONTRACT_INTENTS) == {
        "program_consult", "course_recommend", "policy_qa", "company_info",
        "event_query", "faq", "chitchat", "lead_capture", "transfer_human",
    }


# ── persona prompt ─────────────────────────────────────────────────────

def test_build_persona_message_injects_context():
    """人设模板注入 RAG 上下文。"""
    persona = build_persona_message("[德国] 双元制培训内容...")
    assert "粤教服务" in persona
    assert "双元制培训内容" in persona
    assert "红线" in persona


def test_build_persona_message_empty_context():
    """空上下文时人设模板仍正常组装。"""
    persona = build_persona_message("")
    assert "粤教服务" in persona
    assert "无相关检索结果" in persona


# ── cs_agent_service 开关分流 ──────────────────────────────────────────

class FakeDify:
    """假 Dify 客户端：按预设 answer 返回；LangChain 分支不应调用它。"""

    def __init__(self, answer: str = "[intent:chitchat] 好的"):
        self._answer = answer

    async def chat(self, query, user, conversation_id=None):
        return {"answer": self._answer, "conversation_id": "dify-conv-1"}


class ExplodingDify:
    """哨兵客户端：被调用即失败，验证 LangChain 分支不进 Dify。"""

    async def chat(self, query, user, conversation_id=None):
        raise AssertionError("LangChain 分支不应调用 Dify")


class FakeLangChainEngine:
    """假 LangChain 引擎：模拟分类链 + 回答链，不发起真实 LLM 调用。"""

    async def classify_intent(self, message):
        return {
            "intent": "program_consult",
            "slots": {"name": "王五", "study_intent": "新加坡"},
        }

    async def answer_blocking(self, message, history=None):
        return "您好，关于新加坡项目，我们有定向培养本科班可以推荐 😊"

    async def answer_stream(self, message, history=None):
        yield "您好，关于新加坡项目，我们有定向培养本科班可以推荐 😊"


@pytest_asyncio.fixture
async def cs_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DIFY_CUSTOMER_AGENT_KEY", "test-key")

    async def _noop_publish(*args, **kwargs):
        return 0

    monkeypatch.setattr(event_bus, "publish", _noop_publish)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lc.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        cs_repo = CustomerServiceRepository(session)
        crm_service = CrmService(CrmRepository(session), CustomerRepository(session))
        yield session, cs_repo, crm_service

    await engine.dispose()


async def test_cs_engine_default_dify(cs_env):
    """CS_ENGINE 默认值 = dify（不改变现有行为，可回滚）。"""
    assert settings.CS_ENGINE == "dify"


async def test_dify_branch_still_works(cs_env):
    """CS_ENGINE=dify 时走 Dify 分支，行为与重构前一致。"""
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


async def test_langchain_branch_chat(cs_env, monkeypatch):
    """CS_ENGINE=langchain 时走 LangChain 分支：分类→回答→标记剥离→4出口落库。"""
    session, cs_repo, crm_service = cs_env
    monkeypatch.setattr(settings, "CS_ENGINE", "langchain")

    from app.services import cs_agent_service

    monkeypatch.setattr(cs_agent_service, "_get_langchain_engine", lambda: FakeLangChainEngine())

    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)
    resp = await svc.chat(ChatRequest(message="我想去新加坡读本科，我叫王五"))

    # 意图由分类链输出并经 _finalize_turn 归一
    assert resp.intent == "program_consult"
    # 回答正文（标记已剥离，正文在后）
    assert "新加坡" in resp.answer
    assert "定向培养" in resp.answer
    # 标记未污染前端展示
    assert "[intent:" not in resp.answer
    assert "[SLOTS]" not in resp.answer


async def test_langchain_branch_stream(cs_env, monkeypatch):
    """CS_ENGINE=langchain 时流式分支：token 增量 + done 事件。"""
    session, cs_repo, crm_service = cs_env
    monkeypatch.setattr(settings, "CS_ENGINE", "langchain")

    from app.services import cs_agent_service

    monkeypatch.setattr(cs_agent_service, "_get_langchain_engine", lambda: FakeLangChainEngine())

    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)
    events = [ev async for ev in svc.chat_stream(ChatRequest(message="新加坡项目"))]

    # 必有 meta + token + done
    names = [ev["event"] for ev in events]
    assert names[0] == "meta"
    assert "token" in names
    assert names[-1] == "done"

    # done 携带最终结构化数据
    done = events[-1]["data"]
    assert done["intent"] == "program_consult"
    assert "新加坡" in done["answer"]
