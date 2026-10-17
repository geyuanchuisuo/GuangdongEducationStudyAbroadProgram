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
from app.models.student import StudentPsychAlert, StudentPsychProfile
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
        CustomerAssessment(id=1, customer_id=1, status="valid", sg_conclusion="partial", de_conclusion="not_matched"),
        CustomerAssessment(id=2, customer_id=1, status="valid", sg_conclusion="matched", de_conclusion="not_matched"),
        # 客户2：invalid 研判不算
        CustomerAssessment(id=3, customer_id=2, status="invalid_phone", sg_conclusion="matched", de_conclusion="matched"),
    ])
    await db.commit()

    res = await fetch_customers(db, START, END)
    assert res.status == "ok" and len(res.inputs) == 2  # 无手机号的客户3被排除
    c1 = next(c for c in res.inputs if c.customer_id == 1)
    # 最新 valid 研判（id=2）：4→3 保守映射 matched→符合、not_matched→不符合
    assert c1.sg_conclusion == "符合" and c1.de_conclusion == "不符合"
    assert c1.status_at_period_end == "LOST" and c1.status_source == "auto" and c1.reflowed is True
    c2 = next(c for c in res.inputs if c.customer_id == 2)
    assert c2.sg_conclusion is None  # 仅 invalid 研判 → 无有效结论 → 信息不足由计算器归


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


# ── 投诉域：不可得 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_complaints_unavailable(db):
    res = await fetch_complaints(db, START, END)
    assert res.status == "data_unavailable" and res.inputs == []
    assert "9" in res.note  # 明确写出缺 9 字段


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

    # 投诉周报：必取域 data_unavailable → 拒绝生成
    with pytest.raises(ValidationError):
        await svc.generate("complaint_weekly", past_start, past_end, user_id=1)


@pytest.mark.asyncio
async def test_production_read_failed_rejects_without_mock_fallback(monkeypatch):
    monkeypatch.setattr(settings, "REPORT_DATA_SOURCE", "production")
    svc = rs_module.ReportService(ReportRepository(_BrokenDB()))  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as ei:
        await svc.generate("psych_weekly", START, END, user_id=1)
    assert "不可用" in str(ei.value.message)  # 显式拒绝，不回落 mock


@pytest.mark.asyncio
async def test_mock_provider_default_unchanged(db, monkeypatch):
    monkeypatch.setattr(settings, "REPORT_DATA_SOURCE", "mock")
    svc = rs_module.ReportService(ReportRepository(db))
    report = await svc.generate("psych_weekly", None, None, user_id=1)
    assert report.data_source_status == "mock"
