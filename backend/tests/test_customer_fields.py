async def test_customer_fact_fields_persist_on_create(client, login):
    """CRM 建档时 8 个研判画像字段应落库到 customer 主表。"""
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads",
        json={
            "name": "张三",
            "phone": "13900000001",
            "economy": "年收入30万",
            "needs": "本科升学",
            "study_intent": "想去新加坡",
            "german_ability": "零基础",
            "english_ability": "良好",
            "closed_training": "接受",
            "criminal_record": "无",
            "belt_and_road": "了解",
        },
        headers=headers,
    )
    body = resp.json()
    assert body["code"] == 200, body
    customer_id = body["data"]["lead"]["customer_id"]

    r = await client.get(f"/api/v1/customers/{customer_id}", headers=headers)
    data = r.json()["data"]
    assert data["economy"] == "年收入30万"
    assert data["needs"] == "本科升学"
    assert data["study_intent"] == "想去新加坡"
    assert data["german_ability"] == "零基础"
    assert data["english_ability"] == "良好"
    assert data["closed_training"] == "接受"
    assert data["criminal_record"] == "无"
    assert data["belt_and_road"] == "了解"


async def test_customer_fact_fields_update_sync(client, login):
    """CRM 更新线索时 8 个字段应增量同步到已存在客户。"""
    headers = await login("employee01")
    resp = await client.post(
        "/api/v1/crm/leads", json={"name": "李四", "phone": "13900000002"}, headers=headers
    )
    lead_id = resp.json()["data"]["lead"]["id"]
    customer_id = resp.json()["data"]["lead"]["customer_id"]

    r = await client.put(
        f"/api/v1/crm/leads/{lead_id}",
        json={"economy": "年收入50万", "study_intent": "想去德国"},
        headers=headers,
    )
    assert r.json()["code"] == 200, r.text

    r2 = await client.get(f"/api/v1/customers/{customer_id}", headers=headers)
    data = r2.json()["data"]
    assert data["economy"] == "年收入50万"
    assert data["study_intent"] == "想去德国"
