async def test_create_lead_and_dedup(client, login):
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads",
        json={"customer_name": "张三", "phone": "13800000001", "source": "客服"},
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 200, body
    assert body["data"]["created"] is True
    lead_id = body["data"]["lead"]["id"]

    # 同号 upsert：不重复建档，增量更新
    resp2 = await client.post(
        "/api/v1/crm/leads",
        json={"customer_name": "张三(改)", "phone": "13800000001", "background_info": "补充"},
        headers=headers,
    )
    body2 = resp2.json()
    assert body2["code"] == 200, body2
    assert body2["data"]["created"] is False
    assert body2["data"]["lead"]["id"] == lead_id
    assert body2["data"]["lead"]["customer_name"] == "张三(改)"
    assert body2["data"]["lead"]["background_info"] == "补充"


async def test_status_transition(client, login):
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads", json={"customer_name": "李四", "phone": "13800000002"}, headers=headers
    )
    lead_id = resp.json()["data"]["lead"]["id"]

    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "跟进中"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "已转化"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    # 终态回退应被拒
    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "跟进中"}, headers=headers)
    assert r.json()["code"] == 40002, r.text


async def test_permission_isolation(client, login):
    emp1 = await login("employee01")
    emp2 = await login("employee02")
    mgr = await login("manager01")

    resp = await client.post(
        "/api/v1/crm/leads", json={"customer_name": "王五", "phone": "13800000003"}, headers=emp1
    )
    lead_id = resp.json()["data"]["lead"]["id"]

    # 员工只见自己名下
    r = await client.get("/api/v1/crm/leads", headers=emp2)
    assert r.json()["code"] == 200
    assert r.json()["data"]["total"] == 0

    # 他人无权访问详情
    r = await client.get(f"/api/v1/crm/leads/{lead_id}", headers=emp2)
    assert r.json()["code"] == 40301, r.text

    # 经理可见
    r = await client.get(f"/api/v1/crm/leads/{lead_id}", headers=mgr)
    assert r.json()["code"] == 200, r.text


async def test_follow_up(client, login):
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads", json={"customer_name": "赵六", "phone": "13800000004"}, headers=headers
    )
    lead_id = resp.json()["data"]["lead"]["id"]

    r = await client.post(
        f"/api/v1/crm/leads/{lead_id}/follow-ups",
        json={"content": "电话回访一次", "follow_up_type": "电话"},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text
    assert len(r.json()["data"]["follow_up_history"]) == 1


async def test_assessment_crud(client, login):
    headers = await login("employee01")
    r = await client.post(
        "/api/v1/crm/assessments",
        json={"customer_name": "钱七", "extracted_info": {"phone": "13800000005"}, "is_valid": True},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text
    aid = r.json()["data"]["id"]
    assert r.json()["data"]["is_valid"] is True

    r2 = await client.get(f"/api/v1/crm/assessments/{aid}", headers=headers)
    assert r2.json()["code"] == 200
    assert r2.json()["data"]["customer_name"] == "钱七"


async def test_requires_auth(client):
    r = await client.get("/api/v1/crm/leads")
    assert r.json()["code"] == 40101, r.text
