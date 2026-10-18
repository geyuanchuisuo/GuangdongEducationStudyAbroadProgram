"""P5 FAQ 前置匹配（_match_faq）：命中即秒回原文，不经 Dify。

覆盖：精确问法命中与短路、去标点容错、keywords 改写召回、
未命中落 Dify、多候选最优选择（v6.11.3 回归资产）、
种子答案敏感信息守卫（v6.10.7 缴费账号口径拍板）。
"""
import json
import re
from pathlib import Path

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base
from app.models.customer_service import CsChatMessage, CsFaq
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.cs_agent_service import AiService
from app.services.crm_service import CrmService
from app.services.event_bus import event_bus


class ExplodingDify:
    """哨兵客户端：FAQ 命中路径绝不应进 Dify，一旦调用即失败。"""

    async def chat(self, query, user, conversation_id=None):
        raise AssertionError("FAQ 命中不应进 Dify")


class FakeDify:
    """假 Dify 客户端：按预设 answer 返回，不发起真实 HTTP 请求。"""

    def __init__(self, answer: str):
        self._answer = answer

    async def chat(self, query, user, conversation_id=None):
        return {"answer": self._answer, "conversation_id": "dify-conv-1"}


@pytest_asyncio.fixture
async def faq_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DIFY_CUSTOMER_AGENT_KEY", "test-key")

    async def _noop_publish(*args, **kwargs):
        return 0

    monkeypatch.setattr(event_bus, "publish", _noop_publish)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'faq.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        cs_repo = CustomerServiceRepository(session)
        crm_service = CrmService(CrmRepository(session), CustomerRepository(session))
        yield session, cs_repo, crm_service

    await engine.dispose()


async def _add_faq(session: AsyncSession, **kwargs) -> CsFaq:
    faq = CsFaq(**kwargs)
    session.add(faq)
    await session.commit()
    return faq


async def test_match_faq_company_abbreviation_short_circuits_dify(faq_env):
    """「公司简称是什么？」命中 FAQ 原文秒回，不进 Dify，附 faq 卡片。"""
    session, cs_repo, crm_service = faq_env
    faq = await _add_faq(
        session,
        category=None,
        question="公司简称是什么？",
        answer="简称“粤教服务”",
        keywords="公司,简称,粤教服务",
        sort_order=0,
        enabled=True,
    )
    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)

    resp = await svc.chat(ChatRequest(message="公司简称是什么？"))

    assert resp.intent == "faq"
    assert resp.answer == "简称“粤教服务”"
    assert resp.card_data == {
        "faq": {
            "faq_id": faq.id,
            "category": None,
            "question": "公司简称是什么？",
            "answer": "简称“粤教服务”",
        }
    }

    msgs = (await session.execute(select(CsChatMessage).where(CsChatMessage.role == "assistant"))).scalars().all()
    assert len(msgs) == 1
    assert msgs[0].content == "简称“粤教服务”"
    assert msgs[0].card_data == resp.card_data


async def test_match_faq_punctuation_tolerant(faq_env):
    """去掉问号（_strip_punct 后 Jaccard 同样命中）也应命中。"""
    session, cs_repo, crm_service = faq_env
    await _add_faq(
        session,
        question="公司简称是什么？",
        answer="简称“粤教服务”",
        keywords="公司,简称,粤教服务",
    )
    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)

    resp = await svc.chat(ChatRequest(message="公司简称是什么"))

    assert resp.intent == "faq"
    assert resp.answer == "简称“粤教服务”"


async def test_match_faq_keywords_paraphrase(faq_env):
    """改写问法（Jaccard 不足）靠 keywords 召回：公司+简称 2 个关键词命中。"""
    session, cs_repo, crm_service = faq_env
    await _add_faq(
        session,
        question="公司简称是什么？",
        answer="简称“粤教服务”",
        keywords="公司,简称,粤教服务",
    )
    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)

    resp = await svc.chat(ChatRequest(message="你们公司的简称"))

    assert resp.intent == "faq"
    assert resp.answer == "简称“粤教服务”"


async def test_match_faq_no_hit_falls_through_to_dify(faq_env):
    """无关问题不误命中，正常落 Dify（intent=chitchat、无卡片）。"""
    session, cs_repo, crm_service = faq_env
    await _add_faq(
        session,
        question="公司简称是什么？",
        answer="简称“粤教服务”",
        keywords="公司,简称,粤教服务",
    )
    svc = AiService(cs_repo, dify=FakeDify("[intent:chitchat] 你好呀"), crm_service=crm_service)

    resp = await svc.chat(ChatRequest(message="今天天气怎么样"))

    assert resp.intent == "chitchat"
    assert resp.card_data is None


async def test_match_faq_best_score_selection(faq_env):
    """多候选时选得分最高者：德国问题命中德国条目而非公司简称。"""
    session, cs_repo, crm_service = faq_env
    await _add_faq(
        session,
        question="公司简称是什么？",
        answer="简称“粤教服务”",
        keywords="公司,简称,粤教服务",
    )
    german = await _add_faq(
        session,
        question="德国项目有哪些优势?",
        answer="省属教育国企直接签协议、银行全额低息贷款、国内外全程保姆式服务。",
    )
    svc = AiService(cs_repo, dify=ExplodingDify(), crm_service=crm_service)

    resp = await svc.chat(ChatRequest(message="德国项目有哪些优势?"))

    assert resp.intent == "faq"
    assert resp.answer == german.answer
    assert resp.card_data["faq"]["faq_id"] == german.id


def test_seed_answers_contain_no_bank_account():
    """v6.10.7 业务拍板：缴费账号统一「引导联系顾问」，种子答案不得含银行账号（防回退守卫）。"""
    seed = json.loads((Path(__file__).parents[1] / "scripts" / "cs_faq_seed.json").read_text(encoding="utf-8"))
    for row in seed:
        assert "9550889900011455492" not in row["answer"], row["question"]
        assert not re.search(r"(?<!\d)\d{16,19}(?!\d)", row["answer"]), row["question"]

    pay_rows = [r for r in seed if "缴费账号" in r["question"]]
    assert pay_rows, "缴费账号条目缺失"
    assert "联系顾问" in pay_rows[0]["answer"] and "对公转账" in pay_rows[0]["answer"]
