async def test_create_lead_and_dedup(client, login):
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads",
        json={"name": "张三", "phone": "13800000001", "source": "客服"},
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 200, body
    assert body["data"]["created"] is True
    first_customer_id = body["data"]["lead"]["customer_id"]
    assert first_customer_id is not None

    # 同号 upsert：客户不重复建档（customer_id 不变），但每次新建一条线索
    resp2 = await client.post(
        "/api/v1/crm/leads",
        json={"name": "张三(改)", "phone": "13800000001", "background_info": "补充"},
        headers=headers,
    )
    body2 = resp2.json()
    assert body2["code"] == 200, body2
    assert body2["data"]["created"] is False
    assert body2["data"]["lead"]["customer_id"] == first_customer_id
    assert body2["data"]["lead"]["background_info"] == "补充"


async def test_status_transition(client, login):
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads", json={"name": "李四", "phone": "13800000002"}, headers=headers
    )
    lead_id = resp.json()["data"]["lead"]["id"]

    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "processing"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "converted"}, headers=headers)
    assert r.json()["code"] == 200, r.text
    # 终态回退应被拒
    r = await client.patch(f"/api/v1/crm/leads/{lead_id}/status", json={"status": "processing"}, headers=headers)
    assert r.json()["code"] == 40002, r.text


async def test_permission_isolation(client, login):
    emp1 = await login("employee01")
    emp2 = await login("employee02")
    mgr = await login("manager01")

    resp = await client.post(
        "/api/v1/crm/leads", json={"name": "王五", "phone": "13800000003"}, headers=emp1
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
        "/api/v1/crm/leads", json={"name": "赵六", "phone": "13800000004"}, headers=headers
    )
    lead_id = resp.json()["data"]["lead"]["id"]

    r = await client.post(
        f"/api/v1/crm/leads/{lead_id}/follow-ups",
        json={"content": "电话回访一次", "follow_type": "电话"},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text
    assert r.json()["data"]["content"] == "电话回访一次"
    assert r.json()["data"]["follow_type"] == "电话"


async def test_assessment_crud(client, login):
    headers = await login("employee01")
    r = await client.post(
        "/api/v1/crm/assessments",
        json={"status": "valid", "sg_conclusion": "matched", "score": 90, "overview": "钱七，本科，新加坡意向"},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text
    aid = r.json()["data"]["id"]
    assert r.json()["data"]["sg_conclusion"] == "matched"

    r2 = await client.get(f"/api/v1/crm/assessments/{aid}", headers=headers)
    assert r2.json()["code"] == 200
    assert r2.json()["data"]["overview"] == "钱七，本科，新加坡意向"


async def test_requires_auth(client):
    r = await client.get("/api/v1/crm/leads")
    assert r.json()["code"] == 40101, r.text
