"""客户转留学生端到端测试（方案 A：M1 订阅 approval.approved 事件）

用法：
    python tests/e2e_convert_test.py

前置：
    - 后端已启动（localhost:8000）
    - 已执行 seed_data（MANAGER=13810000004 / EMPLOYEE=13810000003，密码 Test@123456）

验证点：
    1. PROSPECT 注册 → 经理审批通过 → 用户激活为 PROSPECT
    2. 员工发起 convert 审批 → 经理审批通过
    3. 事件总线触发 M1 handler：user.user_type PROSPECT→STUDENT，customer.status→ENROLLED
    4. 转换后用户可登录且 user_type=STUDENT
"""
import sys
from datetime import datetime

import httpx

BASE = "http://localhost:8000/api/v1"
PWD = "Test@123456"
TAG = datetime.now().strftime("%H%M%S")

PASSED = 0
FAILED = 0
FAILURES: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = ""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        FAILURES.append((name, detail))
        print(f"  FAIL {name} -> {detail}")


def call(client, method, path, token=None, body=None, expect=(200,), params=None):
    headers = {"Connection": "close"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = client.request(method, BASE + path, json=body, headers=headers, params=params, timeout=30)
    except Exception as exc:
        return False, {"code": -1, "message": f"请求异常: {exc}"}
    try:
        bj = r.json()
    except Exception:
        bj = {"code": r.status_code, "message": r.text[:200]}
    ok = r.status_code == 200 and bj.get("code") in expect
    return ok, bj


client = httpx.Client()

print("=" * 60)
print("Section 1: 登录核心账号")
print("=" * 60)

ok, bj = call(client, "POST", "/auth/login", body={"username": "13810000004", "password": PWD})
check("登录 MANAGER", ok, str(bj)[:160])
mgr_tok = bj["data"]["access_token"] if ok else None
mgr_id = bj["data"]["user_id"] if ok else None

ok, bj = call(client, "POST", "/auth/login", body={"username": "13810000003", "password": PWD})
check("登录 EMPLOYEE", ok, str(bj)[:160])
emp_tok = bj["data"]["access_token"] if ok else None

if not (mgr_tok and emp_tok):
    print("登录失败，中止")
    sys.exit(1)

print()
print("=" * 60)
print("Section 2: PROSPECT 注册 + 经理审批激活")
print("=" * 60)

prospect_phone = f"1{TAG}0008"
prospect_username = f"e2e_prospect_{TAG}"
ok, bj = call(client, "POST", "/auth/register", body={
    "username": prospect_username,
    "password": PWD,
    "real_name": "转化测试客户",
    "user_type": "PROSPECT",
    "phone": prospect_phone,
    "contact_info": prospect_phone,
})
check("PROSPECT 注册", ok and bj.get("data", {}).get("status") == "待审批", str(bj)[:160])
prospect_user_id = bj.get("data", {}).get("user_id")
prospect_approval_id = bj.get("data", {}).get("approval_id")
prospect_customer_id = bj.get("data", {}).get("customer_id")
check("注册返回 approval_id + customer_id",
      bool(prospect_approval_id and prospect_customer_id),
      f"approval_id={prospect_approval_id} customer_id={prospect_customer_id}")

# 经理审批 prospect_register
ok, bj = call(client, "POST", "/auth/prospect/approve", mgr_tok,
              params={"approval_id": prospect_approval_id, "action": "approve"})
check("经理审批 PROSPECT 注册通过", ok, str(bj)[:160])

# 验证 PROSPECT 可登录
ok, bj = call(client, "POST", "/auth/login", body={"username": prospect_username, "password": PWD})
check("PROSPECT 激活后可登录", ok and bj.get("data", {}).get("user_type") == "PROSPECT",
      f"user_type={bj.get('data', {}).get('user_type')}")

print()
print("=" * 60)
print("Section 3: 员工发起 convert 审批")
print("=" * 60)

ok, bj = call(client, "POST", "/employee/convert-applies", emp_tok, body={
    "customer_id": prospect_customer_id,
    "approver_id": mgr_id,
    "title": f"E2E 转化申请：{prospect_username}",
})
check("员工发起 convert 审批", ok, str(bj)[:160])
convert_approval_id = bj.get("data", {}).get("approval_id")
check("convert 审批单创建成功", bool(convert_approval_id),
      f"approval_id={convert_approval_id}")

print()
print("=" * 60)
print("Section 4: 经理审批 convert → 验证身份转换")
print("=" * 60)

# 审批前查询客户状态
ok, bj = call(client, "GET", f"/customers/{prospect_customer_id}", emp_tok)
before_status = bj.get("data", {}).get("status") if ok else None
check(f"审批前客户状态={before_status}", before_status is not None, str(bj)[:160])

# 经理审批通过
ok, bj = call(client, "POST", f"/approvals/{convert_approval_id}/approve", mgr_tok,
              body={"comment": "E2E 同意转化"})
check("经理审批 convert 通过", ok, str(bj)[:160])

# 验证1：客户状态变为 ENROLLED
ok, bj = call(client, "GET", f"/customers/{prospect_customer_id}", emp_tok)
after_status = bj.get("data", {}).get("status") if ok else None
check("客户状态 → ENROLLED", after_status == "ENROLLED",
      f"实际 status={after_status}")

# 验证2：用户类型变为 STUDENT（重新登录验证）
ok, bj = call(client, "POST", "/auth/login", body={"username": prospect_username, "password": PWD})
after_user_type = bj.get("data", {}).get("user_type") if ok else None
check("用户类型 PROSPECT → STUDENT", after_user_type == "STUDENT",
      f"实际 user_type={after_user_type}")

print()
print("=" * 60)
total = PASSED + FAILED
print(f"RESULT: {PASSED}/{total} passed, {FAILED} failed")
if FAILURES:
    print("失败明细：")
    for name, detail in FAILURES:
        print(f"  - {name}: {detail}")
if FAILED == 0:
    print("ALL TESTS PASSED")
print("=" * 60)
sys.exit(1 if FAILED else 0)
