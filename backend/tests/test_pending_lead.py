async def test_pending_lead_crud_and_merge(client, login):
    """待补全线索：建档 → 查询 → 合并建档客户，合并后从 pending 列表移除且不可重复合并。"""
    headers = await login("employee01")

    # 建档
    resp = await client.post(
        "/api/v1/customers/pending-leads",
        json={"wechat": "wx_test", "name": "待补全", "raw_info": "只有微信号"},
        headers=headers,
    )
    assert resp.json()["code"] == 200, resp.text
    lead_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "pending"

    # 查询
    r = await client.get("/api/v1/customers/pending-leads", headers=headers)
    assert r.json()["code"] == 200
    assert r.json()["data"]["total"] == 1

    # 合并（补手机号建档，归当前员工）
    r = await client.post(
        f"/api/v1/customers/pending-leads/{lead_id}/merge",
        json={"phone": "13600000001", "name": "王五", "education": "本科"},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text
    assert r.json()["data"]["status"] == "merged"
    merged_customer_id = r.json()["data"]["merged_customer_id"]
    assert merged_customer_id is not None

    # 合并后 pending 列表为空
    r = await client.get("/api/v1/customers/pending-leads", headers=headers)
    assert r.json()["data"]["total"] == 0

    # 重复合并应被拒（40901）
    r = await client.post(
        f"/api/v1/customers/pending-leads/{lead_id}/merge",
        json={"phone": "13600000001"},
        headers=headers,
    )
    assert r.json()["code"] == 40901, r.text
