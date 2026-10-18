async def test_chat_unconfigured(client, monkeypatch):
    # 未配置 DIFY_CUSTOMER_AGENT_KEY，应返回业务错误 50001
    # v6.10.0：用 monkeypatch 隔离本地 .env——本用例不再依赖「环境未配 key」前提，任何环境都可复现
    from app.config import settings
    monkeypatch.setattr(settings, "DIFY_CUSTOMER_AGENT_KEY", "")
    r = await client.post("/api/v1/ai/customer-service/chat", json={"message": "你好"})
    assert r.json()["code"] == 50001, r.text
