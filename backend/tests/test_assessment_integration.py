async def test_text_valid(client, login):
    headers = await login("employee01")
    r = await client.post(
        "/api/v1/crm/assessments/text",
        json={"content": "姓名张三，电话13800138000，22岁，本科毕业，想去新加坡留学，希望提升就业竞争力"},
        headers=headers,
    )
    body = r.json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "valid"
    assert body["data"]["customer"]["phone"] == "13800138000"


async def test_text_invalid_phone(client, login):
    headers = await login("employee01")
    r = await client.post(
        "/api/v1/crm/assessments/text",
        json={"content": "姓名张三，19岁，本科毕业，想去新加坡留学"},
        headers=headers,
    )
    body = r.json()
    assert body["code"] == 200, body
    assert body["data"]["status"] == "invalid_phone"


async def test_text_requires_auth(client):
    r = await client.post(
        "/api/v1/crm/assessments/text", json={"content": "姓名张三，电话13800138000"}
    )
    assert r.json()["code"] == 40101, r.text


async def test_save_requires_auth(client):
    r = await client.post(
        "/api/v1/crm/assessments/save",
        json={"record": {"index": 1, "status": "valid", "customer": {"name": "张三", "phone": "13800138000"}}},
    )
    assert r.json()["code"] == 40101, r.text


async def test_save_valid_creates_assessment_and_dedup_lead(client, login):
    headers = await login("employee01")
    record = {
        "index": 1,
        "status": "valid",
        "customer": {"name": "张三", "phone": "13800138009", "gender": "男", "age": "22岁", "education": "本科毕业"},
        "assessments": {"singapore": {"conclusion": "matched"}, "germany": {"conclusion": "partial"}},
        "recommended_projects": [{"project": "singapore", "reason": "年龄、学历与当前需求匹配"}],
        "customer_overview": "张三，男，22岁，本科毕业。",
        "follow_up_advice": "电话切入：围绕升学规划了解目标。",
    }
    r = await client.post(
        "/api/v1/crm/assessments/save",
        json={"record": record, "source_type": "text"},
        headers=headers,
    )
    body = r.json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["is_valid"] is True
    assert data["status"] == "completed"
    assert data["phone"] == "13800138009"
    assert data["lead_id"] is not None
    assert data["match_score"] is None
    assert data["matched_products"] == [{"project": "singapore", "reason": "年龄、学历与当前需求匹配"}]

    # 同号再存：线索 upsert 不重复建档，lead_id 不变
    r2 = await client.post(
        "/api/v1/crm/assessments/save",
        json={"record": record, "source_type": "text"},
        headers=headers,
    )
    body2 = r2.json()
    assert body2["code"] == 200, body2
    assert body2["data"]["lead_id"] == data["lead_id"]

    # 线索仅一条（去重生效）
    r3 = await client.get("/api/v1/crm/leads", headers=headers)
    assert r3.json()["data"]["total"] == 1


async def test_save_invalid_does_not_create_lead(client, login):
    headers = await login("employee01")
    record = {
        "index": 1,
        "status": "invalid_phone",
        "invalid_reason": "未提取到电话号码",
        "customer": {"name": "李四"},
    }
    r = await client.post(
        "/api/v1/crm/assessments/save",
        json={"record": record, "source_type": "text"},
        headers=headers,
    )
    body = r.json()
    assert body["code"] == 200, body
    assert body["data"]["is_valid"] is False
    assert body["data"]["lead_id"] is None
    assert body["data"]["invalid_reason"] == "未提取到电话号码"

    # invalid 不建档
    r2 = await client.get("/api/v1/crm/leads", headers=headers)
    assert r2.json()["data"]["total"] == 0
