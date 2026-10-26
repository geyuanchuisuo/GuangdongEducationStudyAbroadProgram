"""知识问答（RAG /knowledge/ask）服务与接口测试：检索与模型网关均 mock（环境隔离）。

覆盖三态降级链：model（网关正常）/ retrieval_only（网关失败或零命中）/
unavailable（Milvus 不可用），以及 SSE 端点的事件序列。
v6.14.0：链路检索升级为双集合（search_dual），改写层在本文件统一短路（独立覆盖见
test_query_rewrite_and_dual.py）。
"""

import pytest

from app.schemas.knowledge import KnowledgeItem, KnowledgeSearchResponse
from app.services import query_rewriter as qr_module
from app.services.knowledge_qa_service import knowledge_qa_service
from app.services.knowledge_service import knowledge_service


@pytest.fixture(autouse=True)
def _skip_rewrite(monkeypatch):
    """问答链路测试统一跳过改写层（不连外网；改写行为在专项文件覆盖）。"""
    monkeypatch.setattr(qr_module.query_rewriter, "rewrite", lambda q: (q, False))


def _search_response(kb_source: str = "milvus", n: int = 2) -> KnowledgeSearchResponse:
    items = [
        KnowledgeItem(
            content=f"资料片段 {i}",
            category="留学政策",
            source_file="新加坡留学政策指南.docx",
            section="签证要求",
            doc_type="doc",
            score=0.9 - i * 0.1,
        )
        for i in range(n)
    ]
    return KnowledgeSearchResponse(kb_source=kb_source, items=items, total=len(items))


def _forbid_gateway(monkeypatch):
    """网关不应被调用时挂上哨兵。"""

    async def boom(name):
        raise AssertionError(f"gateway should not be called ({name})")

    async def boom_stream(messages):
        raise AssertionError("gateway should not be called (stream)")
        yield  # pragma: no cover - 使其成为异步生成器

    monkeypatch.setattr(knowledge_qa_service, "_stream_gateway", boom_stream)
    monkeypatch.setattr(knowledge_qa_service, "_chat_gateway", boom)


async def test_ask_unavailable_when_milvus_down(monkeypatch):
    monkeypatch.setattr(knowledge_service, "search_dual", lambda q, k=5, c=None: _search_response("unavailable", 0))
    _forbid_gateway(monkeypatch)
    result = await knowledge_qa_service.ask("新加坡签证")
    assert result.answer_source == "unavailable"
    assert result.answer
    assert result.items == []


async def test_ask_retrieval_only_on_zero_hits(monkeypatch):
    # 检索正常但零命中：不调网关，固定提示 + retrieval_only
    monkeypatch.setattr(knowledge_service, "search_dual", lambda q, k=5, c=None: _search_response("milvus", 0))
    _forbid_gateway(monkeypatch)
    result = await knowledge_qa_service.ask("完全不相关的问题")
    assert result.answer_source == "retrieval_only"
    assert "未找到" in result.answer


async def test_ask_retrieval_only_when_gateway_down(monkeypatch):
    monkeypatch.setattr(knowledge_service, "search_dual", lambda q, k=5, c=None: _search_response())

    async def bad_stream(messages):
        raise RuntimeError("gateway down")
        yield  # pragma: no cover

    async def bad_chat(messages):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(knowledge_qa_service, "_stream_gateway", bad_stream)
    monkeypatch.setattr(knowledge_qa_service, "_chat_gateway", bad_chat)
    result = await knowledge_qa_service.ask("新加坡签证")
    assert result.answer_source == "retrieval_only"
    assert len(result.items) == 2  # 降级返回检索原文片段
    assert len(result.sources) == 2


async def test_ask_model_stream_ok(monkeypatch):
    monkeypatch.setattr(knowledge_service, "search_dual", lambda q, k=5, c=None: _search_response())

    async def good_stream(messages):
        yield "新加坡签证需要"
        yield "资金证明与录取通知书。"

    async def not_used(messages):  # pragma: no cover - 流式成功不应走非流式
        raise AssertionError("non-stream fallback should not run")

    monkeypatch.setattr(knowledge_qa_service, "_stream_gateway", good_stream)
    monkeypatch.setattr(knowledge_qa_service, "_chat_gateway", not_used)

    result = await knowledge_qa_service.ask("新加坡签证需要什么")
    assert result.answer_source == "model"
    assert result.answer == "新加坡签证需要资金证明与录取通知书。"
    assert [s.category for s in result.sources] == ["留学政策", "留学政策"]
    assert result.items == []  # 正常生成不重复返回片段


async def test_ask_stream_event_sequence(monkeypatch):
    monkeypatch.setattr(knowledge_service, "search_dual", lambda q, k=5, c=None: _search_response())

    async def good_stream(messages):
        yield "回答A"
        yield "回答B"

    monkeypatch.setattr(knowledge_qa_service, "_stream_gateway", good_stream)

    events = [ev async for ev in knowledge_qa_service.ask_stream("问题", 5)]
    names = [e["event"] for e in events]
    assert names == ["meta", "token", "token", "done"]
    assert events[0]["data"]["total"] == 2
    assert events[1]["delta"] == "回答A"
    assert events[3]["data"]["answer_source"] == "model"


async def test_ask_endpoint_ok(client, monkeypatch):
    from app.schemas.knowledge import KnowledgeAskResponse

    async def fake_ask(question, top_k=5):
        return KnowledgeAskResponse(
            answer="测试回答", answer_source="model",
            sources=[{"category": "公司信息", "source_file": "企业信息.md",
                      "section": "部门架构", "doc_type": "doc", "score": 0.8}],
            total=1,
        )

    monkeypatch.setattr(knowledge_qa_service, "ask", fake_ask)
    resp = await client.post("/api/v1/knowledge/ask", json={"question": "公司简称是什么"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["answer_source"] == "model"
    assert data["answer"] == "测试回答"
    assert data["sources"][0]["source_file"] == "企业信息.md"


async def test_ask_endpoint_stream_sse(client, monkeypatch):
    async def fake_stream(question, top_k=5):
        yield {"event": "meta", "data": {"sources": [], "total": 1}}
        yield {"event": "token", "delta": "你好"}
        yield {"event": "done", "data": {"answer": "你好", "answer_source": "model", "sources": [], "total": 1}}

    monkeypatch.setattr(knowledge_qa_service, "ask_stream", fake_stream)
    resp = await client.post("/api/v1/knowledge/ask/stream", json={"question": "你好"})
    assert resp.status_code == 200
    text = resp.text
    assert "event: meta" in text
    assert "event: token" in text
    assert "event: done" in text
    assert '"delta": "你好"' in text
    assert resp.headers["content-type"].startswith("text/event-stream")


async def test_ask_endpoint_validation(client):
    # 空问题被 Pydantic 拒绝（FastAPI 默认 422，与全站校验行为一致）
    resp = await client.post("/api/v1/knowledge/ask", json={"question": ""})
    assert resp.status_code == 422
