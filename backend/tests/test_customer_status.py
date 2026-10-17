async def test_customer_6state_transition(client, login):
    """客户 6 态流转：NEW→FOLLOWING→STRONG，中文状态值归一化，非法回退被拒。"""
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/customers", json={"phone": "13700000001", "name": "状态测试"}, headers=headers
    )
    assert resp.json()["code"] == 200, resp.text
    cid = resp.json()["data"]["id"]

    r = await client.patch(f"/api/v1/customers/{cid}/status", json={"status": "FOLLOWING"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    assert r.json()["data"]["status"] == "FOLLOWING"

    # 中文状态值归一化到英文编码
    r = await client.patch(f"/api/v1/customers/{cid}/status", json={"status": "意向强烈"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    assert r.json()["data"]["status"] == "STRONG"

    # STRONG 不能回退到 NEW
    r = await client.patch(f"/api/v1/customers/{cid}/status", json={"status": "NEW"}, headers=headers)
    assert r.json()["code"] == 40002, r.text


async def test_customer_status_invalid(client, login):
    """非法状态值应返回参数错误 40002。"""
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/customers", json={"phone": "13700000002", "name": "非法状态"}, headers=headers
    )
    cid = resp.json()["data"]["id"]
    r = await client.patch(f"/api/v1/customers/{cid}/status", json={"status": "不存在"}, headers=headers)
    assert r.json()["code"] == 40002, r.text
