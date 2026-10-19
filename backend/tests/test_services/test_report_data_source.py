"""M5 批次 C（真实数据适配器 + provider 开关）专项测试。

SQLite 真库（create_all）验证适配器查询与 production 生成路径；
mock 回归不受影响（REPORT_DATA_SOURCE 默认 mock）。
"""
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.exceptions import ValidationError
from app.models import Base
from app.models.crm import CustomerAssessment
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport
from app.models.student import StudentFeedbackTicket, StudentPsychAlert, StudentPsychProfile
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.services import report_service as rs_module
from app.services.report_data_source import (
    DomainReadError,
    fetch_complaints,
    fetch_customers,
    fetch_employees_and_daily_reports,
    fetch_psych,
)

START = datetime(2026, 10, 12)
END = datetime(2026, 10, 19)


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ds.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _seed_customer(cid: int, phone: str, **kw) -> Customer:
    base = dict(id=cid, phone=phone, name=f"客{cid}", source_channel="WEBSITE_REGISTER",
                status="NEW", first_register_at=datetime(2026, 10, 13, 9))
    base.update(kw)
    return Customer(**base)


# ── 客户域 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_customers_maps_latest_valid_assessment(db):
    db.add_all([
        _seed_customer(1, "13800000001", status="LOST", auto_churned=True, reflowed_at=datetime(2026, 10, 14)),
        _seed_customer(2, "13800000002"),
        _seed_customer(3, None),  # 无手机号不计（无效）
    ])
    db.add_all([
        # 客户1：两条 valid 研判，id 大的是最新（matched）
        # 注意：created_at 必须显式落在周期内——模型默认填 now()，跑测日期 >= END(2026-10-19) 时
        # 会被"周期后研判不用于该周期"过滤掉，造成时间炸弹（2026-10-19 实测踩雷，LOG-078）
        CustomerAssessment(id=1, customer_id=1, status="valid", sg_conclusion="partial", de_conclusion="not_matched", created_at=datetime(2026, 10, 14, 10)),
        CustomerAssessment(id=2, customer_id=1, status="valid", sg_conclusion="matched", de_conclusion="not_matched", created_at=datetime(2026, 10, 15, 10)),
        # 客户2：invalid 研判不算
        CustomerAssessment(id=3, customer_id=2, status="invalid_phone", sg_conclusion="matched", de_conclusion="matched", created_at=datetime(2026, 10, 16, 10)),
    ])
    await db.commit()

    res = await fetch_customers(db, START, END)
    assert res.status == "ok" and len(res.inputs) == 2  # 无手机号的客户3被排除
    c1 = next(c for c in res.inputs if c.customer_id == 1)
    # v6.11.0：画像四类映射 matched→符合、not_matched→不符合
    assert c1.sg_conclusion == "符合" and c1.de_conclusion == "不符合"
    # v6.11.0：M1 无历史时点 → 期末状态一律不可得，不用当前值冒充
    assert c1.status_at_period_end is None and c1.status_source is None
    assert c1.reflowed is True
    assert "status_at_period_end" in res.unavailable_fields
    assert "不可得" in res.note
    c2 = next(c for c in res.inputs if c.customer_id == 2)
    assert c2.sg_conclusion is None  # 仅 invalid 研判 → 无有效结论（无研判不补值）


@pytest.mark.asyncio
async def test_fetch_customers_read_failure_raises(db):
    class _Broken:
        async def execute(self, *a, **k):
            raise RuntimeError("db down")
    with pytest.raises(DomainReadError):
        await fetch_customers(_Broken(), START, END)  # type: ignore[arg-type]


# ── 员工/日报域 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_employees_and_reports(db):
    db.add_all([
        User(id=11, username="e1", password_hash="x", real_name="员1", user_type="EMPLOYEE",
             department="咨询部", status="正常"),
        User(id=12, username="e2", password_hash="x", real_name="员2", user_type="EMPLOYEE",
             department="教务部", status="禁用"),  # 禁用不计入在职
    ])
    db.add_all([
        EmployeeDailyReport(employee_id=11, report_date=datetime(2026, 10, 13).date(),
                            content="日报", status="submitted"),
        EmployeeDailyReport(employee_id=11, report_date=datetime(2026, 10, 14).date(),
                            content="草稿", status="draft"),  # 不计（另一日期避开同日唯一约束）
        EmployeeDailyReport(employee_id=11, report_date=datetime(2026, 10, 20).date(),
                            content="周期外", status="submitted"),  # 周期外不计
    ])
    await db.commit()

    emp_res, rep_res = await fetch_employees_and_daily_reports(db, START, END)
    assert emp_res.status == "ok" and [e.employee_id for e in emp_res.inputs] == [11]
    assert rep_res.status == "ok" and len(rep_res.inputs) == 1
    assert rep_res.inputs[0].department == "咨询部" and rep_res.inputs[0].is_valid is True


# ── 心理域 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_psych_merges_alert_and_profile(db):
    db.add_all([
        StudentPsychAlert(id=1, student_id=21, trigger_reason="低落", risk_level="高",
                          teacher_id=5, create_time=datetime(2026, 10, 13, 10)),
        StudentPsychProfile(student_id=22, latest_emotion_tag="平稳",
                            last_interaction_time=datetime(2026, 10, 14, 10)),
        StudentPsychProfile(student_id=21, latest_emotion_tag="焦虑",
                            last_interaction_time=datetime(2026, 10, 12, 10)),  # 已有预警覆盖
    ])
    await db.commit()

    res = await fetch_psych(db, START, END)
    assert res.status == "ok" and len(res.inputs) == 2  # 学生21（预警）+ 学生22（画像）
    a = next(r for r in res.inputs if r.student_id == 21)
    assert a.risk_level == "高" and a.responsible_employee_id == 5
    p = next(r for r in res.inputs if r.student_id == 22)
    assert p.emotion_tag == "平稳" and p.risk_level is None


# ── 投诉域：部分可用 + 缺字段标不可得（v6.11.0） ──────────

@pytest.mark.asyncio
async def test_fetch_complaints_partial_fields_marked_unavailable(db):
    res = await fetch_complaints(db, START, END)
    # 空库：可读但无工单 → empty（不再整体 data_unavailable）
    assert res.status == "empty" and res.inputs == []
    # 缺的字段必须显式标不可得，不填零
    for field in ("first_response_at", "satisfaction", "owner_id"):
        assert field in res.unavailable_fields
    assert "不可得字段" in res.note


@pytest.mark.asyncio
async def test_fetch_complaints_counts_rows_instead_of_silent_skip(db):
    """防回退（v6.11.15）：漏 import ComplaintReportInput 曾让全部投诉行被逐行容错
    静默吞掉（NameError 当脏行跳过，报告仍 completed）——周期内真实工单必须进 inputs。"""
    db.add_all([
        User(id=31, username="13800000031", password_hash="x", real_name="测三十一",
             user_type="STUDENT", phone="13800000031"),
        StudentFeedbackTicket(id=201, student_id=31, content="课程退费投诉",
                              status="待处理", create_time=datetime(2026, 10, 14, 9)),
    ])
    await db.commit()

    res = await fetch_complaints(db, START, END)
    assert res.status == "ok"
    assert len(res.inputs) == 1, f"投诉行被静默跳过: {res.note}"
    row = res.inputs[0]
    assert row.ticket_id == 201
    assert row.submitted_at == datetime(2026, 10, 14, 9)
    assert row.status == "open"  # 待处理 → 未解决
    assert row.category_source == "unknown"  # 无 AI 分析记录


# ── production 生成路径 ──────────────────────────────────

class _BrokenDB:
    async def execute(self, *a, **k):
        raise RuntimeError("db down")


@pytest.mark.asyncio
async def test_production_generate_psych_ok_and_complaint_rejected(db, monkeypatch):
    monkeypatch.setattr(settings, "REPORT_DATA_SOURCE", "production")
    # 用一个已过去的自然周（10-05 周一 ~ 10-12 下周一），避免未来周期校验拦截
    past_start, past_end = datetime(2026, 10, 5), datetime(2026, 10, 12)
    db.add_all([
        StudentPsychAlert(id=1, student_id=21, trigger_reason="低落", risk_level="高",
                          teacher_id=5, create_time=datetime(2026, 10, 6, 10)),
    ])
    await db.commit()

    svc = rs_module.ReportService(ReportRepository(db))
    report = await svc.generate("psych_weekly", past_start, past_end, user_id=1)
    assert report.status == "completed" and report.data_source_status == "production"
    content = report.report_content
    assert content["data_quality"]["psych"] == "ok"
    assert content["metrics"]["covered_students"] == 1
    # 数据质量标注进入口径说明（投诉域不可得等）
    assert "投诉域" in content["data_notes"]

    # 投诉周报：v6.11.0 改为部分生成（缺字段标不可得），不再整体拒绝
    complaint = await svc.generate("complaint_weekly", past_start, past_end, user_id=1)
    assert complaint.status == "completed"
    c_content = complaint.report_content
    assert c_content["data_quality"]["complaints"] in ("ok", "empty")
    assert c_content["data_unavailable"]["complaints"]  # 缺字段显式列在报告里
    assert c_content["metrics"]["orders_total"] == 0


@pytest.mark.asyncio
async def test_production_read_failed_marks_unavailable_without_mock_fallback(db, monkeypatch):
    """v6.11.0：读取失败不再整体拒绝——报告照常生成但标不可得，且绝不回落 mock。"""
    monkeypatch.setattr(settings, "REPORT_DATA_SOURCE", "production")
    # M0 未登记报告专用 Agent，因此本用例不依赖真实 Dify。

    async def _boom(*a, **k):
        raise DomainReadError("psych db down")

    monkeypatch.setattr(rs_module, "fetch_psych", _boom)
    svc = rs_module.ReportService(ReportRepository(db))
    # 用已过去的自然周，避免未来周期校验先拦下来
    past_start, past_end = datetime(2026, 10, 5), datetime(2026, 10, 12)
    report = await svc.generate("psych_weekly", past_start, past_end, user_id=1)
    content = report.report_content
    assert report.status == "completed" and report.data_source_status == "production"
    assert content["data_quality"]["psych"] == "read_failed"
    assert content["ai_status"] == "unavailable" and content["ai_source"] == "unavailable"
    assert "读取失败" in content["data_notes"]
    # 关键：失败域只影响自己，不吃掉整份报告，也没有回落 mock 文本
    assert "（模拟）" not in str(content.get("summary") or "")


@pytest.mark.asyncio
async def test_mock_provider_default_unchanged(db, monkeypatch):
    monkeypatch.setattr(settings, "REPORT_DATA_SOURCE", "mock")
    svc = rs_module.ReportService(ReportRepository(db))
    report = await svc.generate("psych_weekly", None, None, user_id=1)
    assert report.data_source_status == "mock"
