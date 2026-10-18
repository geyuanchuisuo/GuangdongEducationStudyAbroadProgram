"""M5 批次 E（M5-10.1）——/reports 7 端点权限矩阵与入参边界（SQLite API 测试）。

权限模型（HTTP 200 信封 + 业务码）：
- MANAGER/ADMIN：全部 7 端点可用
- EMPLOYEE：仅 psych_cases 可用（只看自己负责）；其余 40301
- 边界：非法 report_type → 422（schema Literal）；page_size>100 → 422
"""
import pytest


@pytest.mark.asyncio
async def test_report_api_matrix(client, login):
    manager = await login("manager01")

    # 生成（默认参考周期，mock）
    resp = await client.post("/api/v1/reports/generate", json={"report_type": "psych_weekly"},
                             headers=manager)
    assert resp.json()["code"] == 200, resp.text
    report_id = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "completed"
    assert resp.json()["data"]["data_source_status"] == "mock"

    # 列表（含瘦身断言：条目无 report_content）
    resp = await client.get("/api/v1/reports", headers=manager)
    body = resp.json()
    assert body["code"] == 200 and body["data"]["total"] >= 1
    assert all("report_content" not in item for item in body["data"]["items"])

    # 详情
    resp = await client.get(f"/api/v1/reports/{report_id}", headers=manager)
    assert resp.json()["code"] == 200
    assert resp.json()["data"]["report_content"]["ai_status"] in ("available", "unavailable")

    # 下钻：类型不匹配 → 40002
    resp = await client.get(f"/api/v1/reports/{report_id}/customers", headers=manager)
    assert resp.json()["code"] == 40002
    # 下钻：心理个案（manager 全量）
    resp = await client.get(f"/api/v1/reports/{report_id}/psych_cases", headers=manager)
    assert resp.json()["code"] == 200

    # 下载 PDF
    resp = await client.get(f"/api/v1/reports/{report_id}/download", headers=manager)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_report_api_employee_permissions(client, login):
    employee = await login("employee01")
    manager = await login("manager01")
    # 经理先造一条报告
    resp = await client.post("/api/v1/reports/generate", json={"report_type": "psych_weekly"},
                             headers=manager)
    report_id = resp.json()["data"]["id"]

    # EMPLOYEE：管理端点全部 40301
    for method, path in [
        ("GET", "/api/v1/reports"),
        ("POST", "/api/v1/reports/generate"),
        ("GET", f"/api/v1/reports/{report_id}"),
        ("GET", f"/api/v1/reports/{report_id}/customers"),
        ("GET", f"/api/v1/reports/{report_id}/special_cases"),
        ("GET", f"/api/v1/reports/{report_id}/download"),
    ]:
        if method == "GET":
            resp = await client.get(path, headers=employee)
        else:
            resp = await client.post(path, json={"report_type": "psych_weekly"}, headers=employee)
        assert resp.json()["code"] == 40301, f"{method} {path}: {resp.text}"

    # EMPLOYEE：心理个案可用，且只看到自己负责的个案（按 responsible_employee_id 过滤）
    resp = await client.get(f"/api/v1/reports/{report_id}/psych_cases", headers=employee)
    assert resp.json()["code"] == 200
    me = (await client.get("/api/v1/users/me", headers=employee)).json()["data"]
    my_id = me["id"]
    items = resp.json()["data"]["items"]
    assert all(item["responsible_employee_id"] == my_id for item in items)
    # 且严格少于经理视角的全量（过滤确实生效）
    resp_manager = await client.get(f"/api/v1/reports/{report_id}/psych_cases", headers=manager)
    assert len(items) < len(resp_manager.json()["data"]["items"])


@pytest.mark.asyncio
async def test_report_api_param_boundaries(client, login):
    manager = await login("manager01")
    # 非法 report_type（契约旧笔误值）→ schema Literal → 422
    resp = await client.post("/api/v1/reports/generate", json={"report_type": "customer_business"},
                             headers=manager)
    assert resp.status_code == 422
    # 前端 code 也 422
    resp = await client.post("/api/v1/reports/generate", json={"report_type": "CA"}, headers=manager)
    assert resp.status_code == 422
    # page_size 超上限 → 422
    resp = await client.get("/api/v1/reports?page_size=200", headers=manager)
    assert resp.status_code == 422
    # 不存在的报告 → 40401
    resp = await client.get("/api/v1/reports/99999", headers=manager)
    assert resp.json()["code"] == 40401
