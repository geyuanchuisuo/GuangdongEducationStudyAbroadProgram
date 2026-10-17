"""M3+M4 Docker 端到端测试（v6.8.1）

用法（在 edu-backend 容器内执行）：
    docker exec edu-backend /app/.venv/bin/python tests/e2e_m3m4_test.py

前置：
    - edu-mysql / edu-redis / edu-backend 已启动
    - 已执行 python -m scripts.seed_data（测试账号 user001/user002/user005，密码 123456）
    - MinIO 本轮未启动：跳过文件上传相关用例（记 SKIP）
"""
import asyncio
import io
import sys
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select

sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://localhost:8000/api/v1"
TAG = datetime.now().strftime("%H%M%S")  # 幂等重跑：注册/建号用户名与手机号加运行时间戳
PASSED = 0
FAILED = 0
SKIPPED = 0
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


def skip(name: str, reason: str):
    global SKIPPED
    SKIPPED += 1
    print(f"  SKIP {name} ({reason})")


def call(client: httpx.Client, method: str, path: str, token: str | None = None,
         body=None, params=None, expect=(200,), files=None):
    """请求并校验 HTTP200 + 业务码。expect 为业务码集合。返回 (ok, body)。"""
    # Connection: close 规避 keep-alive 连接复用导致的 "Connection reset" 连锁假象
    headers = {"Connection": "close"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = client.request(method, BASE + path, json=body, params=params,
                           headers=headers, files=files, timeout=30)
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
print("Section 0: 环境与健康检查")
print("=" * 60)
ok, bj = call(client, "GET", "/health".replace("/health", "/../health").replace("/api/v1/..", ""))
# /health 在根路径，不在 /api/v1 下
r = client.get("http://localhost:8000/health")
check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", r.text[:120])

print()
print("=" * 60)
print("Section 1: 认证登录（seed 账号）")
print("=" * 60)
tokens, uids = {}, {}
for uname, utype in [("user001", "MANAGER"), ("user002", "EMPLOYEE"), ("user005", "STUDENT")]:
    ok, bj = call(client, "POST", "/auth/login", body={"username": uname, "password": "123456"})
    check(f"login {uname}({utype})", ok and bj.get("data", {}).get("user_type") == utype, str(bj)[:160])
    if ok:
        tokens[utype] = bj["data"]["access_token"]
        uids[utype] = bj["data"]["user_id"]

mgr_tok, emp_tok, stu_tok = tokens.get("MANAGER"), tokens.get("EMPLOYEE"), tokens.get("STUDENT")
mid, eid, sid = uids.get("MANAGER"), uids.get("EMPLOYEE"), uids.get("STUDENT")
if not (mgr_tok and emp_tok and stu_tok):
    print("登录失败，中止后续测试")
    print(f"RESULT: {PASSED}/{PASSED + FAILED} passed, {FAILED} failed, {SKIPPED} skipped")
    sys.exit(1)


def prepare_student_fixture() -> int | None:
    """测试前置（仅测试库数据准备）：
    1) 把 user002 名下一个客户挂到 user005（sys_user_id），使 M4 提交服务单能解析到负责员工；
    2) 清掉 user005 的种子请假单，保证「新建请假→审批」链路确定；
    3) 清理种子审批实例与新业务 ID 的撞车（种子 biz_id 随机 1~500，生产环境不存在此重叠）。
    """
    from sqlalchemy import delete as sa_delete, update as sa_update

    from app.config import settings
    from app.models.customer import Customer
    from app.models.student import StudentAdminService
    from app.models.system import ApprovalInstance, ApprovalTask
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _q():
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as s:
                cust = (await s.execute(
                    select(Customer).where(Customer.owner_employee_id == eid).order_by(Customer.id.asc())
                )).scalars().first()
                if cust:
                    cust.sys_user_id = sid
                await s.execute(sa_delete(StudentAdminService).where(
                    StudentAdminService.student_id == sid,
                    StudentAdminService.service_type == "请假",
                ))
                # 幂等重跑：上轮 E2E 客户可能已被再分配/状态流转，还原归属与状态（CRM 录入按手机号去重）
                await s.execute(sa_update(Customer).where(
                    Customer.phone.in_(("13900001111", "13900002222"))
                ).values(owner_employee_id=eid, status="新录入"))
                # 种子实例 biz_id 1~500 会与新创建的服务单(>100)/工单(>100)/日报(>120)/客户(>120)撞车
                colliding_rows = (await s.execute(
                    select(ApprovalInstance.id).where(
                        (ApprovalInstance.biz_type == "leave") & (ApprovalInstance.biz_id > 100)
                        | (ApprovalInstance.biz_type == "convert") & (ApprovalInstance.biz_id > 120)
                        | (ApprovalInstance.biz_type == "late_report") & (ApprovalInstance.biz_id > 120)
                        | (ApprovalInstance.biz_type == "complaint") & (ApprovalInstance.biz_id > 100)
                    )
                )).scalars().all()
                if colliding_rows:
                    await s.execute(sa_delete(ApprovalTask).where(ApprovalTask.instance_id.in_(colliding_rows)))
                    await s.execute(sa_delete(ApprovalInstance).where(ApprovalInstance.id.in_(colliding_rows)))
                await s.commit()
                return cust.id if cust else None
        finally:
            await engine.dispose()

    return asyncio.run(_q())


def _free_report_day() -> str:
    """找一个该员工没有日报的历史日期（幂等重跑：固定日期上轮已提交会 40901）。"""
    from app.config import settings
    from app.models.employee import EmployeeDailyReport
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _q():
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as s:
                used = set((await s.execute(
                    select(EmployeeDailyReport.report_date).where(EmployeeDailyReport.employee_id == eid)
                )).scalars().all())
                base = date.today() - timedelta(days=45)
                for i in range(400):
                    cand = base - timedelta(days=i)
                    if cand not in used:
                        return cand
                return base
        finally:
            await engine.dispose()

    return asyncio.run(_q())


linked_customer_id = prepare_student_fixture()
print(f"INFO 测试前置：客户挂接 student->employee（customer_id={linked_customer_id}），种子请假单已清理")

# 员工注册新员工账号（公开注册允许 STUDENT/EMPLOYEE）
ok, bj = call(client, "POST", "/auth/register",
              body={"username": f"e2e_stu01_{TAG}", "password": "e2e123456",
                    "real_name": "端到端学生", "user_type": "STUDENT",
                    "contact_info": f"1{TAG}0002"})
check("register 新账号", ok, str(bj)[:160])

print()
print("=" * 60)
print("Section 2: M4 学生端（user005）")
print("=" * 60)
tomorrow = date.today() + timedelta(days=1)
day_after = date.today() + timedelta(days=2)

# 请假单：前置已清理种子请假单，直接新建（负责员工应为 user002）；再验证防重 40901
ok, bj = call(client, "POST", "/student/admin-services", stu_tok, body={
    "service_type": "请假", "start_time": f"{tomorrow}T09:00:00",
    "end_time": f"{day_after}T18:00:00", "reason": "E2E 测试请假"})
check("M4 提交请假申请", ok, str(bj)[:160])
leave_id = bj.get("data", {}).get("id") if ok else None
if leave_id is not None:
    check("M4 请假审批人解析为负责员工", bj.get("data", {}).get("approver_id") == eid,
          f"approver_id={bj.get('data', {}).get('approver_id')} 期望 {eid}")

# 同学生同时段请假防重（待审批/已通过存在时提交新请假 → 40901）
ok, bj = call(client, "POST", "/student/admin-services", stu_tok, body={
    "service_type": "请假", "start_time": f"{tomorrow}T09:00:00",
    "end_time": f"{day_after}T18:00:00", "reason": "E2E 防重验证"}, expect=(200, 40901))
check("M4 请假防重（重复提交→40901）", ok and bj.get("code") == 40901, str(bj)[:160])

ok, bj = call(client, "GET", "/student/admin-services", stu_tok)
check("M4 请假列表", ok, str(bj)[:160])

ok, bj = call(client, "POST", "/student/psych/chat", stu_tok, body={
    "message": "我最近情绪很低落，压力很大，经常失眠，感到难过和焦虑，不想说话"})
check("M4 心理对话（AI降级预期）", ok, str(bj)[:160])

ok, bj = call(client, "GET", "/student/psych/profile", stu_tok)
check("M4 心理画像", ok, str(bj)[:160])

ok, bj = call(client, "POST", "/student/tickets", stu_tok, body={
    "content": "E2E 测试工单", "detail": "宿舍网络问题需要处理"})
check("M4 提交售后工单", ok, str(bj)[:160])
ticket_id = bj.get("data", {}).get("id") if ok else None

ok, bj = call(client, "GET", "/student/tickets", stu_tok)
check("M4 工单列表", ok, str(bj)[:160])

ok, bj = call(client, "GET", "/student/academic", stu_tok)
check("M4 学业考务聚合", ok and isinstance(bj.get("data", {}).get("upcoming_3d"), list), str(bj)[:160])

ok, bj = call(client, "GET", "/student/progress", stu_tok)
check("M4 进度追踪", ok, str(bj)[:160])

ok, bj = call(client, "GET", "/student/life/faq", stu_tok)
check("M4 生活FAQ", ok, str(bj)[:160])

ok, bj = call(client, "GET", "/student/services", stu_tok)
check("M4 更多服务", ok, str(bj)[:160])

ok, bj = call(client, "POST", "/student/agent/chat", stu_tok, body={"message": "帮我看看最近有什么学业安排"})
check("M4 学生助手Agent（降级预期）", ok, str(bj)[:160])

ok, bj = call(client, "GET", "/student/reminders", stu_tok)
check("M4 提醒聚合", ok, str(bj)[:160])

print()
print("=" * 60)
print("Section 3: M3 普通员工端（user002）")
print("=" * 60)

# 个人信息 / 提醒
ok, bj = call(client, "GET", "/employee/profile", emp_tok)
check("M3 个人信息查询", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/profile/stats", emp_tok)
check("M3 个人统计", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/reminders", emp_tok)
check("M3 提醒聚合", ok, str(bj)[:160])

# 组织架构
ok, bj = call(client, "GET", "/employee/org", emp_tok)
check("M3 组织架构树", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/org/members", emp_tok)
check("M3 同事查询（脱敏）", ok, str(bj)[:160])
if mid:
    ok, bj = call(client, "POST", f"/employee/org/members/{mid}/reveal-phone", emp_tok)
    check("M3 完整电话二次确认（留日志）", ok, str(bj)[:160])

# 日报（历史日期不能直接补提 → 先存草稿再走补报申请，即完整补报链路）
old_day = _free_report_day()
ok, bj = call(client, "POST", "/employee/reports", emp_tok, body={
    "report_date": str(old_day), "content": "E2E 补录日报草稿：回访客户并整理资料", "status": "draft"})
check("M3 存日报草稿（历史日期）", ok, str(bj)[:160])
report_id = bj.get("data", {}).get("id") if ok else None
ok, bj = call(client, "GET", "/employee/reports", emp_tok, params={"page": 1, "page_size": 10})
check("M3 日报列表", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/reports/summary", emp_tok)
check("M3 日报汇总（M5对外接口）", ok, str(bj)[:160])

# 待办
ok, bj = call(client, "POST", "/employee/todos", emp_tok, body={
    "todo_type": "follow_up", "title": "E2E 待办：回访客户"})
check("M3 新建待办", ok, str(bj)[:160])
todo_id = bj.get("data", {}).get("id") if ok else None
if todo_id:
    ok, bj = call(client, "PUT", f"/employee/todos/{todo_id}", emp_tok, body={"status": "done"})
    check("M3 更新待办为完成", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/todos", emp_tok)
check("M3 待办列表", ok, str(bj)[:160])

# CRM 录入 + 状态流转 + 跟进
ok, bj = call(client, "POST", "/employee/crm/leads", emp_tok, body={
    "raw_text": "E2E 客户：张三，高三学生家长，意向德国双元制", "phone": "13900001111",
    "name": "张三E2E", "auto_assess": False})
check("M3 CRM文字录入线索", ok, str(bj)[:160])
cid = bj.get("data", {}).get("customer_id") if ok else None

ok, bj = call(client, "POST", "/employee/crm/leads", emp_tok, body={
    "raw_text": "E2E 客户2：李四，本科毕业，意向新加坡本硕", "phone": "13900002222",
    "name": "李四E2E", "auto_assess": False})
check("M3 CRM第二线索（供转化申请）", ok, str(bj)[:160])
cid2 = bj.get("data", {}).get("customer_id") if ok else None

ok, bj = call(client, "GET", "/employee/customers", emp_tok, params={"page": 1, "page_size": 20})
check("M3 我的客户列表（数据隔离）", ok, str(bj)[:160])

if cid:
    ok, bj = call(client, "PATCH", f"/employee/customers/{cid}/status", emp_tok,
                  body={"status": "跟进中", "reason": "E2E 状态流转"})
    check("M3 客户6态流转（跟进中）", ok, str(bj)[:160])

ok, bj = call(client, "POST", "/employee/crm/follow-ups", emp_tok, body={
    "customer_id": cid or 1, "follow_type": "电话", "content": "E2E 跟进：已电话沟通",
    "next_action": "发送课程资料", "next_date": f"{tomorrow}T10:00:00"})
check("M3 新增跟进记录", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/crm/follow-ups", emp_tok)
check("M3 跟进记录列表", ok, str(bj)[:160])

# 成绩录入
ok, bj = call(client, "POST", "/employee/scores", emp_tok, body={
    "student_id": sid, "course_name": "E2E德语基础", "score": 88.5, "semester": "2026秋季"})
check("M3 成绩录入", ok, str(bj)[:160])

# 学生行政服务审批（审批 Section 2 学生的请假单）
ok, bj = call(client, "GET", "/employee/admin-services", emp_tok, params={"status": "待审批", "page": 1, "page_size": 100})
found = False
if ok:
    for item in bj.get("data", {}).get("items", []):
        if item.get("id") == leave_id:
            found = True
            break
check("M3 待审批服务单查询（含学生请假单）", ok and (leave_id is not None and found), str(bj)[:160])
if leave_id:
    ok, bj = call(client, "POST", f"/employee/admin-services/{leave_id}/review", emp_tok,
                  body={"action": "approve", "comment": "E2E 同意请假"})
    check("M3 审批请假（leave.approved 事件）", ok, str(bj)[:160])

# 投诉工单处理
if ticket_id:
    ok, bj = call(client, "POST", f"/employee/tickets/{ticket_id}/handle", emp_tok,
                  body={"solution": "E2E 已联系宿管处理网络"})
    check("M3 处理工单（complaint.resolved 事件）", ok, str(bj)[:160])
else:
    ok, bj = call(client, "GET", "/employee/tickets", emp_tok, params={"status": "待处理"})
    check("M3 工单列表", ok, str(bj)[:160])

# 心理预警处理（DB 直查一个未处理预警 ID；每次独立建引擎，避免跨事件循环复用连接池）
def _get_alert_id() -> int | None:
    from app.config import settings
    from app.models.student import StudentPsychAlert
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _q():
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as s:
                row = (await s.execute(
                    select(StudentPsychAlert).where(StudentPsychAlert.status == "未处理")
                    .order_by(StudentPsychAlert.id.desc())
                )).scalars().first()
                return row.id if row else None
        finally:
            await engine.dispose()

    return asyncio.run(_q())

alert_id = _get_alert_id()
if alert_id:
    ok, bj = call(client, "POST", f"/employee/psych-alerts/{alert_id}/handle", emp_tok,
                  body={"action": "communicated", "note": "E2E 已沟通安抚"})
    check("M3 心理预警处理", ok, str(bj)[:160])
else:
    skip("M3 心理预警处理", "DB 无未处理预警")

# 导出 CSV
for name, path in [("客户", "/employee/export/customers"), ("日报", "/employee/export/daily-reports"),
                   ("跟进", "/employee/export/follow-ups"), ("工单", "/employee/export/tickets")]:
    try:
        r = client.get(BASE + path, headers={"Authorization": f"Bearer {emp_tok}"}, timeout=30)
        ok = r.status_code == 200 and len(r.content) > 0
        check(f"M3 导出{name}CSV", ok, f"HTTP{r.status_code} len={len(r.content)}")
    except Exception as exc:
        check(f"M3 导出{name}CSV", False, str(exc)[:120])

# 指令式业务（v6.8.3：AI 不可用自动本地规则兜底，不再 50002；当前环境无 Dify，source 预期 local）
ok, bj = call(client, "POST", "/employee/commands/parse", emp_tok, body={
    "text": "给客户12添加一条跟进记录：明天上午电话回访"})
_action = bj.get("data", {}).get("action", {}) if ok else {}
check("M3 指令解析（本地兜底）",
      ok and _action.get("action_type") == "follow_up.create" and _action.get("source") == "local",
      str(bj)[:160])
cmd_token = bj.get("data", {}).get("token") if ok else None
if cmd_token:
    ok, bj = call(client, "POST", "/employee/commands/execute", emp_tok,
                  body={"token": cmd_token, "confirm": False})
    check("M3 指令二次确认-取消", ok and bj.get("data", {}).get("executed") is False, str(bj)[:160])

# 企业助手 Agent + 新人指引（AI 不可用降级预期）
ok, bj = call(client, "POST", "/employee/agent/chat", emp_tok, body={"message": "我今天的待办有哪些"})
check("M3 企业助手Agent（降级预期）", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/guide/onboarding", emp_tok)
check("M3 新人指引", ok, str(bj)[:160])
ok, bj = call(client, "POST", "/employee/guide/ask", emp_tok, body={"question": "怎么提交日报？"})
check("M3 指引问答（本地匹配预期）", ok, str(bj)[:160])

# 日报补报申请（供管理层审批）
late_approval_id = None
if report_id:
    ok, bj = call(client, "POST", f"/employee/reports/{report_id}/late-apply", emp_tok,
                  body={"approver_id": mid}, expect=(200, 40901))
    check("M3 日报补报申请", ok, str(bj)[:160])
    late_approval_id = bj.get("data", {}).get("approval_id") or bj.get("data", {}).get("id")

# 代客申请留学生（走 convert 审批，供管理层批）
if cid2:
    ok, bj = call(client, "POST", "/employee/convert-applies", emp_tok, body={
        "customer_id": cid2, "approver_id": mid, "title": "E2E 转化申请：李四E2E"})
    check("M3 代客申请留学生", ok, str(bj)[:160])
    convert_approval_id = bj.get("data", {}).get("approval_id")
else:
    convert_approval_id = None

print()
print("=" * 60)
print("Section 4: M3 管理层端（user001）")
print("=" * 60)
ok, bj = call(client, "GET", "/employee/dashboard", mgr_tok)
check("M3 经营看板", ok and "overview" in bj.get("data", {}), str(bj)[:160])
ok, bj = call(client, "GET", "/employee/customers", mgr_tok, params={"page": 1, "page_size": 20})
check("M3 全部客户查询", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/employee/customers", mgr_tok, params={"employee_id": eid})
check("M3 按员工下钻客户", ok, str(bj)[:160])

# 审批中心 + 转化审批
ok, bj = call(client, "GET", "/employee/approvals-center", mgr_tok)
check("M3 审批中心聚合视图", ok, str(bj)[:160])
if convert_approval_id:
    ok, bj = call(client, "POST", f"/approvals/{convert_approval_id}/approve", mgr_tok,
                  body={"comment": "E2E 同意转化"})
    check("M3 留学生转化审批通过", ok, str(bj)[:160])
else:
    skip("M3 留学生转化审批通过", "无转化申请单")

# 用户管理
ok, bj = call(client, "POST", "/employee/users", mgr_tok, body={
    "username": f"e2e_emp01_{TAG}", "password": "e2e123456", "real_name": "端到端员工",
    "user_type": "EMPLOYEE", "phone": f"1{TAG}0001", "department": "咨询部"})
check("M3 创建员工账号", ok, str(bj)[:160])
new_uid = bj.get("data", {}).get("id") if ok else None
if new_uid:
    ok, bj = call(client, "PATCH", f"/employee/users/{new_uid}/status", mgr_tok, body={"status": "禁用"})
    check("M3 禁用员工账号", ok, str(bj)[:160])
    ok, bj = call(client, "PATCH", f"/employee/users/{new_uid}/status", mgr_tok, body={"status": "正常"})
    check("M3 恢复员工账号", ok, str(bj)[:160])
    ok, bj = call(client, "PUT", f"/employee/users/{new_uid}/permissions", mgr_tok,
                  body={"permissions": ["report.export"]})
    check("M3 配置权限JSON", ok, str(bj)[:160])

# 操作日志
ok, bj = call(client, "GET", "/operation-logs", mgr_tok, params={"module": "crm"})
check("M3 操作日志查询", ok, str(bj)[:160])

# 日报批示
if report_id:
    ok, bj = call(client, "POST", f"/employee/reports/{report_id}/annotations", mgr_tok,
                  body={"content": "E2E 批示：继续保持"})
    check("M3 日报批示", ok, str(bj)[:160])
    ok, bj = call(client, "GET", f"/employee/reports/{report_id}/annotations", mgr_tok)
    check("M3 查看日报批示", ok, str(bj)[:160])

# 补报审批
if late_approval_id:
    ok, bj = call(client, "POST", "/employee/reports/late-review", mgr_tok, body={
        "approval_id": late_approval_id, "action": "approved", "comment": "E2E 同意补报"})
    check("M3 补报审批", ok, str(bj)[:160])
else:
    skip("M3 补报审批", "无补报审批单")

# 客户再分配（放最后，避免影响前面的归属校验）
if cid:
    employee_list_ok, bj2 = call(client, "GET", "/employee/users", mgr_tok, params={"page": 1, "page_size": 50})
    eid3 = None
    if employee_list_ok:
        items = bj2.get("data", {}).get("items") or []
        for u in items:
            if u.get("username") == "user003":
                eid3 = u.get("id")
                break
        if eid3 is None:
            for u in items:
                if u.get("id") not in (eid, mid):
                    eid3 = u.get("id")
                    break
    if eid3:
        ok, bj = call(client, "POST", "/employee/customers/reassign", mgr_tok, body={
            "from_employee_id": eid, "to_employee_id": eid3, "customer_ids": [cid]})
        check("M3 客户再分配", ok, str(bj)[:160])
    else:
        skip("M3 客户再分配", "无其他员工可转移")

print()
print("=" * 60)
print("Section 5: M4 回路验证（审批/处理结果 + 通知）")
print("=" * 60)
ok, bj = call(client, "GET", "/student/admin-services", stu_tok)
status_now = None
if ok:
    for item in bj.get("data", {}).get("items", []):
        if item.get("id") == leave_id:
            status_now = item.get("status")
            break
check("M4 回路：请假单已被审批（状态≠待审批）",
      status_now is not None and status_now not in ("待审批",), f"实际状态: {status_now}")

ok, bj = call(client, "GET", "/student/tickets", stu_tok)
t_status = None
if ok:
    for item in bj.get("data", {}).get("items", []):
        if item.get("id") == ticket_id:
            t_status = item.get("status")
            break
check("M4 回路：工单已被处理（状态≠待处理）",
      t_status is not None and t_status not in ("待处理",), f"实际状态: {t_status}")

ok, bj = call(client, "GET", "/notifications", stu_tok)
check("M4 通知列表（请假/工单结果）", ok, str(bj)[:160])
ok, bj = call(client, "GET", "/notifications/unread-count", stu_tok)
check("M4 未读通知计数", ok and isinstance(bj.get("data"), (int, dict)), str(bj)[:160])

print()
print("=" * 60)
print("Section 5.5: M5 智能报告链路（MANAGER/EMPLOYEE 权限 + 生成/列表/详情/下钻/PDF）")
print("=" * 60)

# 生成（默认参考周期，mock 数据）
ok, bj = call(client, "POST", "/reports/generate", mgr_tok, body={"report_type": "psych_weekly"})
check("M5 生成心理周报（completed+mock）",
      ok and bj.get("data", {}).get("status") == "completed"
      and bj.get("data", {}).get("data_source_status") == "mock", str(bj)[:160])
report_id = bj.get("data", {}).get("id") if ok else None

# 重复生成 → 版本递增
ok2, bj2 = call(client, "POST", "/reports/generate", mgr_tok, body={"report_type": "psych_weekly"})
check("M5 重复生成版本递增",
      ok2 and bj2.get("data", {}).get("version", 0) > bj.get("data", {}).get("version", 0),
      f"v1={bj.get('data', {}).get('version')} v2={bj2.get('data', {}).get('version')}")
if ok2 and report_id is None:
    report_id = bj2.get("data", {}).get("id")

# 列表（折叠 + 瘦身：条目不含 report_content）
ok, bj = call(client, "GET", "/reports?page_size=20", mgr_tok)
items = bj.get("data", {}).get("items", []) if ok else []
check("M5 列表（≥1 条且条目无 report_content）",
      ok and len(items) >= 1 and all("report_content" not in it for it in items), str(bj)[:160])

# 详情
if report_id:
    ok, bj = call(client, "GET", f"/reports/{report_id}", mgr_tok)
    check("M5 详情（ai_status 合法值）",
          ok and bj.get("data", {}).get("report_content", {}).get("ai_status") in ("available", "unavailable"),
          str(bj)[:160])
    # 心理个案下钻（manager 全量）
    ok, bj = call(client, "GET", f"/reports/{report_id}/psych_cases", mgr_tok)
    check("M5 心理个案下钻（manager）", ok and isinstance(bj.get("data", {}).get("items"), list), str(bj)[:160])

# EMPLOYEE：管理端点 40301；心理个案 200（按负责过滤）
ok, bj = call(client, "GET", "/reports", emp_tok, expect=(200, 40301))
check("M5 EMPLOYEE 列表被拒（40301）", ok and bj.get("code") == 40301, str(bj)[:160])
if report_id:
    ok, bj = call(client, "GET", f"/reports/{report_id}/psych_cases", emp_tok)
    check("M5 EMPLOYEE 心理个案（200，按负责过滤）", ok and bj.get("code") == 200, str(bj)[:160])

# 非法 report_type → HTTP 422（schema Literal 校验）
try:
    r = client.request("POST", BASE + "/reports/generate", json={"report_type": "customer_business"},
                       headers={"Authorization": f"Bearer {mgr_tok}", "Connection": "close"}, timeout=30)
    check("M5 非法 report_type → 422", r.status_code == 422, f"HTTP {r.status_code}")
except Exception as exc:
    check("M5 非法 report_type → 422", False, str(exc))

# PDF 下载（二进制响应，不走 call 的 json 解析）
if report_id:
    try:
        r = client.get(BASE + f"/reports/{report_id}/download",
                       headers={"Authorization": f"Bearer {mgr_tok}", "Connection": "close"}, timeout=30)
        check("M5 下载脱敏 PDF（%PDF 魔数）", r.status_code == 200 and r.content[:4] == b"%PDF",
              f"HTTP {r.status_code} bytes={len(r.content)}")
    except Exception as exc:
        check("M5 下载脱敏 PDF", False, str(exc))

print()
print("=" * 60)
total = PASSED + FAILED
print(f"RESULT: {PASSED}/{total} passed, {FAILED} failed, {SKIPPED} skipped")
if FAILURES:
    print("失败明细：")
    for name, detail in FAILURES:
        print(f"  - {name}: {detail}")
if FAILED == 0:
    print("ALL TESTS PASSED")
print("=" * 60)
sys.exit(1 if FAILED else 0)
