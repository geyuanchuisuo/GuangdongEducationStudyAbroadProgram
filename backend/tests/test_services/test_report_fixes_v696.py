"""M5-10.7~10.9 修复回归（v6.9.6）。

覆盖三项本轮修复：
1. M5-10.8 production 缺省周期 = 上一完整自然周（不再必撞 check_future）
2. M5-10.7 客户 6 态中英归一（复用 M1 词表）+ 取数逐行容错（单行脏数据不拖垮全篇）
3. M5-10.9 下钻与报告同源（production 报告读真实业务表，mock 报告读模拟数据）
"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.crm import AiReport
from app.models.customer import Customer
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.services import report_service as rs_module
from app.services.customer_service import CUSTOMER_STATUSES, STATUS_CN_TO_EN
from app.services.report_data_source import fetch_customers, normalize_customer_status
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset
from app.services.report_service import ReportService
from app.utils.report_period import (
    PeriodValidationError,
    default_completed_week,
    validate_period,
    week_range,
)

# ── M5-10.8 缺省周期 ──────────────────────────────────────


def test_default_completed_week_is_previous_week():
    """周六（2026-10-17）→ 缺省为上一完整自然周 [10-05, 10-12)。"""
    start, end = default_completed_week(datetime(2026, 10, 17, 14, 50))
    assert start == datetime(2026, 10, 5)
    assert end == datetime(2026, 10, 12)
    assert (end - start) == timedelta(days=7)


def test_default_completed_week_passes_future_check():
    """缺省周期必须能过 check_future：这正是当前自然周会失败的地方。"""
    now = datetime.now()
    start, end = default_completed_week(now)
    validate_period(start, end, now=now, check_future=True)  # 不抛即通过
    # 反证：当前自然周的终点恒在未来，必然被拒（修复前的行为）
    this_start, this_end = week_range(now)
    assert this_end > now
    with pytest.raises(PeriodValidationError):
        validate_period(this_start, this_end, now=now, check_future=True)


def test_default_completed_week_aligned_on_any_weekday():
    """周一~周日任意一天取缺省周期，都应是已结束的对齐自然周。"""
    for day in range(7):
        now = datetime(2026, 10, 12, 9) + timedelta(days=day)  # 10-12 是周一
        start, end = default_completed_week(now)
        assert start.weekday() == 0 and (end - start) == timedelta(days=7)
        assert end <= now


# ── M5-10.7 客户状态归一 ──────────────────────────────────


def test_normalize_covers_m1_vocabulary():
    """M1 词表里的每个中文值都必须能归一（单一来源，不另造词表）。"""
    for zh, code in STATUS_CN_TO_EN.items():
        assert normalize_customer_status(zh) == code, zh


def test_normalize_accepts_english_and_unknown():
    for code in CUSTOMER_STATUSES:
        assert normalize_customer_status(code) == code
        assert normalize_customer_status(code.lower()) == code
    assert normalize_customer_status("  跟进中 ") == "FOLLOWING"  # 首尾空白
    assert normalize_customer_status("") is None
    assert normalize_customer_status(None) is None
    assert normalize_customer_status("完全不存在的状态") is None


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fix.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_customers_normalizes_chinese_and_skips_bad_rows(db):
    """中文状态正常参与统计；无法识别的状态只跳过该行，不抛异常、不拖垮整篇。"""
    db.add_all([
        Customer(id=1, phone="13800000001", name="中文态", status="跟进中",
                 first_register_at=datetime(2026, 10, 13, 9)),
        Customer(id=2, phone="13800000002", name="英文态", status="SIGNED",
                 first_register_at=datetime(2026, 10, 13, 9)),
        Customer(id=3, phone="13800000003", name="脏数据", status="状态不存在",
                 first_register_at=datetime(2026, 10, 13, 9)),
    ])
    await db.commit()

    res = await fetch_customers(db, PERIOD_START, PERIOD_END)

    by_id = {i.customer_id: i for i in res.inputs}
    assert set(by_id) == {1, 2}  # 第 3 行被跳过
    assert by_id[1].status_at_period_end == "FOLLOWING"
    assert by_id[2].status_at_period_end == "SIGNED"
    assert "跳过 1 行" in res.note  # 口径说明显式记录跳过
    assert res.status == "ok"


@pytest.mark.asyncio
async def test_fetch_customers_lost_source_uses_normalized_status(db):
    """流失来源判定要基于归一号：中文「已流失」也必须识别为 LOST。"""
    db.add(Customer(id=4, phone="13800000004", name="流失态", status="已流失",
                    auto_churned=True, first_register_at=datetime(2026, 10, 13, 9)))
    await db.commit()

    res = await fetch_customers(db, PERIOD_START, PERIOD_END)
    item = next(i for i in res.inputs if i.customer_id == 4)
    assert item.status_at_period_end == "LOST"
    assert item.status_source == "auto"


# ── M5-10.9 下钻与报告同源 ────────────────────────────────


@pytest_asyncio.fixture
async def svc_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'drill.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _make_report(db, report_type: str, source: str) -> AiReport:
    report = AiReport(
        report_type=report_type,
        report_title="t",
        report_content={"metrics": {}},
        time_range_start=PERIOD_START,
        time_range_end=PERIOD_END,
        generated_by=1,
        status="completed",
        version=1,
        data_source_status=source,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@pytest.mark.asyncio
async def test_psych_drilldown_uses_production_dataset_for_production_report(
    svc_db, monkeypatch
):
    """production 报告的下钻必须走真实取数，而不是恒用 mock 数据集。"""
    report = await _make_report(svc_db, "psych_weekly", "production")
    admin = User(id=1, username="m", password_hash="x", real_name="经理", user_type="MANAGER")
    svc = ReportService(ReportRepository(svc_db))

    prod_ds = build_mock_dataset(PERIOD_START, PERIOD_END)  # 桩数据，仅用于区分来源
    prod_ds.psych_records = [
        r for r in prod_ds.psych_records if r.student_id == 1
    ]
    calls = {"n": 0}

    async def _fake_build(self, report_type, start, end):
        calls["n"] += 1
        return prod_ds, {"psych": "ok"}, ["stub"]

    monkeypatch.setattr(ReportService, "_build_production_dataset", _fake_build)
    items = await svc.psych_cases(report.id, admin)

    assert calls["n"] == 1, "production 报告应触发真实取数"
    assert {i["student_id"] for i in items} == {1}


@pytest.mark.asyncio
async def test_psych_drilldown_uses_mock_dataset_for_mock_report(svc_db, monkeypatch):
    """mock 报告仍用模拟数据，不得触发生产取数。"""
    report = await _make_report(svc_db, "psych_weekly", "mock")
    admin = User(id=1, username="m", password_hash="x", real_name="经理", user_type="MANAGER")
    svc = ReportService(ReportRepository(svc_db))

    async def _should_not_call(self, report_type, start, end):
        raise AssertionError("mock 报告不应走生产取数")

    monkeypatch.setattr(ReportService, "_build_production_dataset", _should_not_call)
    items = await svc.psych_cases(report.id, admin)
    assert len(items) > 0  # 参考周期的 mock 心理记录


@pytest.mark.asyncio
async def test_customer_drilldown_follows_report_source(svc_db, monkeypatch):
    report = await _make_report(svc_db, "customer_analysis", "production")
    svc = ReportService(ReportRepository(svc_db))
    prod_ds = build_mock_dataset(PERIOD_START, PERIOD_END)
    prod_ds.customers = prod_ds.customers[:2]

    async def _fake_build(self, report_type, start, end):
        return prod_ds, {"customers": "ok"}, []

    monkeypatch.setattr(ReportService, "_build_production_dataset", _fake_build)
    items = await svc.customer_drilldown(report.id)
    assert 0 < len(items) <= 2


def test_module_has_no_unused_default_period_helper():
    """防止回退：缺省周期必须来自 default_completed_week，而不是 week_range(now)。"""
    import inspect

    src = inspect.getsource(rs_module)
    assert "default_completed_week(datetime.now())" in src
    assert "period_start or week_range(datetime.now())[0]" not in src
