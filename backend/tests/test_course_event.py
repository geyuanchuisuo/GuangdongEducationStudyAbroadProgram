async def test_list_courses_public(client):
    r = await client.get("/api/v1/courses")
    assert r.json()["code"] == 200
    assert r.json()["data"]["total"] >= 2


async def test_list_events_public(client):
    r = await client.get("/api/v1/events")
    assert r.json()["code"] == 200
    assert r.json()["data"]["total"] >= 2


async def test_event_register_and_duplicate(client, login):
    headers = await login("employee01")
    items = (await client.get("/api/v1/events")).json()["data"]["items"]
    event = next(i for i in items if i["max_participants"] == 100)

    r = await client.post(f"/api/v1/events/{event['id']}/register", headers=headers)
    assert r.json()["code"] == 200, r.text

    # 重复报名被拒
    r2 = await client.post(f"/api/v1/events/{event['id']}/register", headers=headers)
    assert r2.json()["code"] == 40002, r2.text


async def test_event_register_full(client, login):
    emp1 = await login("employee01")
    emp2 = await login("employee02")
    items = (await client.get("/api/v1/events")).json()["data"]["items"]
    event = next(i for i in items if i["max_participants"] == 1)

    r = await client.post(f"/api/v1/events/{event['id']}/register", headers=emp1)
    assert r.json()["code"] == 200, r.text
    # 满员被拒
    r2 = await client.post(f"/api/v1/events/{event['id']}/register", headers=emp2)
    assert r2.json()["code"] == 40002, r2.text


async def test_event_register_requires_auth(client):
    items = (await client.get("/api/v1/events")).json()["data"]["items"]
    r = await client.post(f"/api/v1/events/{items[0]['id']}/register")
    assert r.json()["code"] == 40101, r.text
