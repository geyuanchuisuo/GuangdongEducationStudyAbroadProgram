"""知识检索接口测试：mock 掉 Milvus/Ollama（环境隔离用例，参照 test_ai 模式）。

/knowledge/search 为公开接口；服务层的三态口径（milvus/unavailable）在此验证。
"""

from app.schemas.knowledge import KnowledgeItem, KnowledgeSearchResponse
from app.services.knowledge_service import knowledge_service


def _fake_response(kb_source: str = "milvus", n: int = 2) -> KnowledgeSearchResponse:
    items = [
        KnowledgeItem(
            content=f"切片内容 {i}",
            category="留学政策",
            source_file="新加坡留学政策指南.docx",
            section="签证要求",
            doc_type="doc",
            score=0.9 - i * 0.1,
        )
        for i in range(n)
    ]
    return KnowledgeSearchResponse(kb_source=kb_source, items=items, total=len(items))


async def test_search_ok(client, monkeypatch):
    monkeypatch.setattr(knowledge_service, "search", lambda q, k=5, c=None: _fake_response())
    resp = await client.post(
        "/api/v1/knowledge/search", json={"query": "新加坡签证要求", "top_k": 2}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["kb_source"] == "milvus"
    assert data["total"] == 2
    assert data["items"][0]["category"] == "留学政策"
    assert data["items"][0]["score"] > 0


async def test_search_without_score(client, monkeypatch):
    monkeypatch.setattr(knowledge_service, "search", lambda q, k=5, c=None: _fake_response())
    resp = await client.post(
        "/api/v1/knowledge/search", json={"query": "学费", "with_score": False}
    )
    data = resp.json()["data"]
    assert all(item["score"] is None for item in data["items"])


async def test_search_category_filter_passed(client, monkeypatch):
    captured: dict = {}

    def fake_search(query, top_k=5, categories=None):
        captured["categories"] = categories
        return _fake_response()

    monkeypatch.setattr(knowledge_service, "search", fake_search)
    resp = await client.post(
        "/api/v1/knowledge/search",
        json={"query": "学费", "categories": ["公司业务", "留学政策"]},
    )
    assert resp.json()["code"] == 200
    assert captured["categories"] == ["公司业务", "留学政策"]


async def test_search_invalid_category_rejected(client, monkeypatch):
    # 分类非法应先于服务调用被拒（40002），不触发向量库
    def boom(query, top_k=5, categories=None):  # pragma: no cover - 不应被调用
        raise AssertionError("invalid category should be rejected before service call")

    monkeypatch.setattr(knowledge_service, "search", boom)
    resp = await client.post(
        "/api/v1/knowledge/search", json={"query": "学费", "categories": ["不存在分类"]}
    )
    assert resp.json()["code"] == 40002


async def test_search_unavailable_degrades_gracefully(client, monkeypatch):
    monkeypatch.setattr(
        knowledge_service, "search", lambda q, k=5, c=None: _fake_response("unavailable", 0)
    )
    resp = await client.post("/api/v1/knowledge/search", json={"query": "学费"})
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["kb_source"] == "unavailable"
    assert body["data"]["items"] == []
