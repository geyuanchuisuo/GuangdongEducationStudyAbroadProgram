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


async def test_register_prospect_pending_gate(client, monkeypatch):
    created, _ = _patch_engine(monkeypatch)
    r = await client.post("/api/v1/auth/register", json=PROSPECT)
    body = r.json()
    assert body["code"] == 200, r.text
    assert body["data"]["status"] == "待审批"
    assert body["data"]["approval_id"] == 99
    assert body["data"]["customer_id"] > 0
    # 审批实例携带真实 user/customer 外键
    inst = created["instance"]
    assert inst.initiator_id == body["data"]["user_id"]
    assert inst.biz_id == body["data"]["customer_id"]
    # 待审批登录拦截（v6.10.0：40006 账号待开通，与 40003 禁用区分）
    r2 = await client.post("/api/v1/auth/login", json={"username": PROSPECT["username"], "password": "123456"})
    assert r2.json()["code"] == 40006, r2.text


async def test_approve_prospect_requires_manager_role(client, monkeypatch, login):
    _patch_engine(monkeypatch)
    await client.post("/api/v1/auth/register", json=PROSPECT)
    # 未登录 → 40101
    r0 = await client.post("/api/v1/auth/prospect/approve", params={"approval_id": 99, "action": "approve"})
    assert r0.json()["code"] == 40101, r0.text
    # EMPLOYEE → 40301（v6.10.0：审批人从 JWT 取并校验 MANAGER）
    emp = await login("employee01")
    r1 = await client.post("/api/v1/auth/prospect/approve", params={"approval_id": 99, "action": "approve"}, headers=emp)
    assert r1.json()["code"] == 40301, r1.text


async def test_approve_prospect_approve_flow(client, monkeypatch, login):
    _, published = _patch_engine(monkeypatch)
    reg = (await client.post("/api/v1/auth/register", json=PROSPECT)).json()["data"]
    mgr = await login("manager01")
    r = await client.post(
        "/api/v1/auth/prospect/approve",
        params={"approval_id": reg["approval_id"], "action": "approve"},
        headers=mgr,
    )
    assert r.json()["code"] == 200, r.text
    assert r.json()["data"]["status"] == "approved"
    # 激活后可登录，且发出 customer.registered 事件
    r2 = await client.post("/api/v1/auth/login", json={"username": PROSPECT["username"], "password": "123456"})
    assert r2.json()["code"] == 200, r2.text
    assert r2.json()["data"]["user_type"] == "PROSPECT"
    assert len(published) == 1


async def test_approve_prospect_reject_flow(client, monkeypatch, login):
    _patch_engine(monkeypatch)
    reg = (await client.post("/api/v1/auth/register", json={
        **PROSPECT, "username": "13800000002", "phone": "13800000002", "contact_info": "13800000002",
    })).json()["data"]
    mgr = await login("manager01")
    r = await client.post(
        "/api/v1/auth/prospect/approve",
        params={"approval_id": reg["approval_id"], "action": "reject"},
        headers=mgr,
    )
    assert r.json()["code"] == 200, r.text
    # 驳回后禁用登录拦截（40003 与待审批 40006 区分）
    r2 = await client.post("/api/v1/auth/login", json={"username": "13800000002", "password": "123456"})
    assert r2.json()["code"] == 40003, r2.text
