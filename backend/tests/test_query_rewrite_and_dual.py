"""v6.14.0：问题改写层（智能路由 + DeepSeek + 回退）与双集合检索单元测试（全 mock）。"""

from app.schemas.knowledge import KnowledgeItem, KnowledgeSearchResponse
from app.services import query_rewriter as qr_mod
from app.services.query_rewriter import QueryRewriter, needs_rewrite
from app.services.knowledge_service import knowledge_service


# ---- 智能路由 needs_rewrite ---------------------------------------------------

def test_route_short_query_skipped():
    # 超短/专有名词查询不送改写（防改坏 IHK、2+2 等）
    assert needs_rewrite("IHK") is False
    assert needs_rewrite("2+2") is False
    assert needs_rewrite("B1") is False


def test_route_normal_question_skipped():
    # 已含疑问结构的规范问句直接跳过，省延迟
    assert needs_rewrite("新加坡2+2国际本科班的学费总共大概多少？") is False
    assert needs_rewrite("去德国参加双元制职业培训需要什么条件？") is False
    assert needs_rewrite("德国项目优势有哪些") is False


def test_route_vague_question_triggered():
    # 口语化模糊问句（无疑问词、无问号）才送改写
    assert needs_rewrite("学费贵不贵啊") is True
    assert needs_rewrite("想去新加坡读书") is True
    assert needs_rewrite("德国双元制那个项目感觉挺好的") is True


def test_route_pure_symbols_skipped():
    assert needs_rewrite("？？？") is False
    assert needs_rewrite("。。。") is False


# ---- 改写执行与回退 ------------------------------------------------------------

def _patch_gateway(monkeypatch, content: str | None, raise_exc: Exception | None = None):
    def fake_post(url, headers=None, json=None, timeout=None):
        class Resp:
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": content}}]}
        if raise_exc:
            raise raise_exc
        return Resp()

    monkeypatch.setattr(qr_mod.httpx, "post", fake_post)


def test_rewrite_success(monkeypatch):
    _patch_gateway(monkeypatch, "新加坡留学项目的学费和学制是怎样的")
    rewriter = QueryRewriter()
    rewritten, changed = rewriter.rewrite("想去新加坡读书")
    assert changed is True
    assert rewritten == "新加坡留学项目的学费和学制是怎样的"


def test_rewrite_failure_falls_back(monkeypatch):
    _patch_gateway(monkeypatch, None, raise_exc=RuntimeError("gateway down"))
    rewriter = QueryRewriter()
    rewritten, changed = rewriter.rewrite("学费贵不贵啊")
    assert changed is False
    assert rewritten == "学费贵不贵啊"


def test_rewrite_empty_output_falls_back(monkeypatch):
    _patch_gateway(monkeypatch, "   ")
    rewriter = QueryRewriter()
    rewritten, changed = rewriter.rewrite("这个项目怎么样值不值")
    assert changed is False
    assert rewritten == "这个项目怎么样值不值"


def test_rewrite_skipped_returns_original(monkeypatch):
    _forbid = lambda *a, **k: (_ for _ in ()).throw(AssertionError("gateway should not be called"))
    monkeypatch.setattr(qr_mod.httpx, "post", _forbid)
    rewriter = QueryRewriter()
    rewritten, changed = rewriter.rewrite("IHK")
    assert changed is False
    assert rewritten == "IHK"


# ---- 双集合检索（search_dual 全 mock，验证 RRF 融合与 source 标记） ----------------

def _hit(entity: dict, distance: float = 0.0) -> dict:
    return {"distance": distance, "entity": entity}


def test_search_dual_rrf_merge(monkeypatch):
    # FAQ 库与长文库各返回 1 条：RRF 下两库 rank1 同分并列在前
    def fake_hybrid(collection, query, top_k, filter_expr, output_fields):
        if collection == "yuejiao_faq":
            return [_hit({"question": "公司简称是什么？", "answer": "简称粤教服务",
                          "category": "公司信息", "source_file": "常见问答对.xlsx"})]
        return [_hit({"content": "粤教服务是……", "category": "公司信息",
                      "source_file": "企业信息.md", "section": "公司简介", "doc_type": "doc"})]

    monkeypatch.setattr(knowledge_service, "ensure_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "ensure_faq_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "_hybrid_search_one", fake_hybrid)

    result = knowledge_service.search_dual("公司简称", top_k=2)
    assert result.kb_source == "milvus"
    assert result.total == 2
    sources = {it.source for it in result.items}
    assert sources == {"faq", "knowledge"}
    faq_item = next(it for it in result.items if it.source == "faq")
    assert "公司简称是什么" in faq_item.content
    assert faq_item.doc_type == "faq"
    # 两库 rank1 的 RRF 分数相同
    kb_item = next(it for it in result.items if it.source == "knowledge")
    assert faq_item.score == kb_item.score


def test_search_dual_one_side_down(monkeypatch):
    # 单库失败不影响另一路：FAQ 挂了仍返回长文结果
    def fake_hybrid(collection, query, top_k, filter_expr, output_fields):
        if collection == "yuejiao_faq":
            raise RuntimeError("faq down")
        return [_hit({"content": "长文内容", "category": "留学政策",
                      "source_file": "德国留学政策指南.docx", "section": "签证", "doc_type": "doc"})]

    monkeypatch.setattr(knowledge_service, "ensure_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "ensure_faq_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "_hybrid_search_one", fake_hybrid)

    result = knowledge_service.search_dual("签证要求", top_k=5)
    assert result.kb_source == "milvus"
    assert result.total == 1
    assert result.items[0].source == "knowledge"


def test_search_dual_both_down_unavailable(monkeypatch):
    def boom(collection, query, top_k, filter_expr, output_fields):
        raise RuntimeError("all down")

    monkeypatch.setattr(knowledge_service, "ensure_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "ensure_faq_collection", lambda: None)
    monkeypatch.setattr(knowledge_service, "_hybrid_search_one", boom)

    result = knowledge_service.search_dual("学费", top_k=5)
    assert result.kb_source == "unavailable"
    assert result.items == []
