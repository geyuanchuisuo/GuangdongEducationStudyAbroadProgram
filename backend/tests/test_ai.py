async def test_chat_unconfigured(client):
    # 未配置 DIFY_CUSTOMER_AGENT_KEY，应返回业务错误 50001
    r = await client.post("/api/v1/ai/customer-service/chat", json={"message": "你好"})
    assert r.json()["code"] == 50001, r.text
