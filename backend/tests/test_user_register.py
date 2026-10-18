"""v6.10.0：注册/审批门 API 级单测（v6.9.11~v6.9.13 此前零覆盖，schema 漏改即由此漏检）。

审批引擎/事件总线为 M0 全局单例（自带会话直连配置库），单测中用 fake 替换，
不触碰 M0 代码；用户/客户读写走请求会话（SQLite 内存库），完全隔离。
"""
from app.services import approval_engine as approval_engine_module
from app.services import event_bus as event_bus_module


class FakeInstance:
    def __init__(self, id, biz_type="prospect_register", status="pending", initiator_id=None, biz_id=None):
        self.id = id
        self.biz_type = biz_type
        self.status = status
        self.initiator_id = initiator_id
        self.biz_id = biz_id


def _patch_engine(monkeypatch):
    """替换审批引擎与事件总线为进程内 fake，返回 (created, published) 供断言。"""
    created: dict = {}
    published: list = []

    async def fake_create(**kwargs):
        inst = FakeInstance(id=99, initiator_id=kwargs.get("initiator_id"), biz_id=kwargs.get("biz_id"))
        created["instance"] = inst
        return inst

    async def fake_process(instance_id, approver_id, comment=None):
        return FakeInstance(id=instance_id, status="approved")

    async def fake_get(instance_id):
        return created.get("instance")

    async def fake_publish(*args, **kwargs):
        published.append(args)

    monkeypatch.setattr(approval_engine_module.approval_engine, "create", fake_create)
    monkeypatch.setattr(approval_engine_module.approval_engine, "approve", fake_process)
    monkeypatch.setattr(approval_engine_module.approval_engine, "reject", fake_process)
    monkeypatch.setattr(approval_engine_module.approval_engine, "get_by_id", fake_get)
    monkeypatch.setattr(event_bus_module.event_bus, "publish", fake_publish)
    return created, published


PROSPECT = {
    "username": "13800000001",
    "password": "123456",
    "real_name": "测试客户",
    "user_type": "PROSPECT",
    "contact_info": "13800000001",
    "phone": "13800000001",
    "wechat": "test_wx01",
    "age": 20,
    "education": "本科",
}


async def test_register_student_ok_and_login(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "stu01", "password": "123456", "real_name": "学生一", "user_type": "STUDENT",
    })
    assert r.json()["code"] == 200, r.text
    r2 = await client.post("/api/v1/auth/login", json={"username": "stu01", "password": "123456"})
    assert r2.json()["code"] == 200, r2.text
    assert r2.json()["data"]["user_type"] == "STUDENT"


async def test_register_duplicate_username(client):
    body = {"username": "dup01", "password": "123456", "real_name": "重复用户", "user_type": "STUDENT"}
    assert (await client.post("/api/v1/auth/register", json=body)).json()["code"] == 200
    assert (await client.post("/api/v1/auth/register", json=body)).json()["code"] == 40002


async def test_register_prospect_rejects_prospect_type_before_v913(client, monkeypatch):
    # v6.9.13 起注册契约放行 PROSPECT（schema 漏改回归哨兵：pattern 若回退本用例即失败）。
    # 引擎同样要打桩：本用例只验证契约层，不打桩会穿透到真实 MySQL（M0 引擎自带会话）
    _patch_engine(monkeypatch)
    r = await client.post("/api/v1/auth/register", json=PROSPECT)
    assert r.json()["code"] != 422, "PROSPECT 应被注册契约接受（v6.9.13 schema 补齐）"


async def test_register_prospect_is_immediately_active(client, monkeypatch):
    _, published = _patch_engine(monkeypatch)
    r = await client.post("/api/v1/auth/register", json=PROSPECT)
    body = r.json()
    assert body["code"] == 200, r.text
    assert body["data"]["status"] == "正常"
    assert "approval_id" not in body["data"]
    assert body["data"]["customer_id"] > 0

    login = await client.post("/api/v1/auth/login", json={"username": PROSPECT["username"], "password": "123456"})
    assert login.json()["code"] == 200, login.text
    assert login.json()["data"]["user_type"] == "PROSPECT"
    assert len(published) == 1


async def test_register_prospect_customer_event_payload(client, monkeypatch):
    _, published = _patch_engine(monkeypatch)
    r = await client.post("/api/v1/auth/register", json={**PROSPECT, "username": "13800000002", "phone": "13800000002", "contact_info": "13800000002"})
    assert r.json()["code"] == 200, r.text
    event = published[0]
    assert event[1] == "M1"
    assert event[2]["phone"] == "13800000002"
