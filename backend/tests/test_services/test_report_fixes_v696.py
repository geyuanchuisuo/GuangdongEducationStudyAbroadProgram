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
@pytest.mark.asyncio
async def test_fetch_customers_status_unavailable_but_rows_kept(db):
    """v6.11.0：期末状态不可得（不用当前值冒充），中文/英文/未知状态都不再影响取数。"""
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

    # 三行都保留（状态不再参与字面量校验），但期末状态一律 None
    assert {i.customer_id for i in res.inputs} == {1, 2, 3}
    assert all(i.status_at_period_end is None for i in res.inputs)
    assert all(i.status_source is None for i in res.inputs)
    assert "status_at_period_end" in res.unavailable_fields
    assert res.status == "ok"


@pytest.mark.asyncio
async def test_status_normalizer_kept_as_defense(db):
    """接口化后仍保留归一号作防御（上游若返回中文，M5 能自行归一）。"""
    assert normalize_customer_status("已流失") == "LOST"
    assert normalize_customer_status("跟进中") == "FOLLOWING"
    assert normalize_customer_status("SIGNED") == "SIGNED"
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
@pytest.mark.asyncio
async def test_psych_drilldown_reads_snapshot_not_live_data(svc_db, monkeypatch):
    """v6.11.0 §2.2：下钻只读生成时固化的快照，旧报告不再查实时数据。"""
    report = await _make_report(svc_db, "psych_weekly", "production")
    admin = User(id=1, username="m", password_hash="x", real_name="经理", user_type="MANAGER")
    svc = ReportService(ReportRepository(svc_db))

    async def _should_not_call(self, report_type, start, end):
        raise AssertionError("下钻不得再触发实时取数")

    monkeypatch.setattr(ReportService, "_build_production_dataset", _should_not_call)
    items, note = await svc.psych_cases(report.id, admin)

    # 该报告由 _make_report 直接插入（无快照）→ 返回空 + 明确提示，不回查实时库
    assert items == []
    assert "无下钻快照" in note


@pytest.mark.asyncio
async def test_drill_snapshot_written_on_generate(svc_db):
    """生成报告时写入下钻快照，之后读下钻只读快照。"""
    svc = ReportService(ReportRepository(svc_db))
    report = await svc.generate("psych_weekly", PERIOD_START, PERIOD_END, user_id=1)
    from app.models.crm import AiReportDrill
    from sqlalchemy import select
    rows = (await svc_db.execute(
        select(AiReportDrill).where(AiReportDrill.report_id == report.id)
    )).scalars().all()
    assert len(rows) == 1 and rows[0].drill_type == "psych_cases"
    assert rows[0].row_count > 0

    admin = User(id=1, username="m", password_hash="x", real_name="经理", user_type="MANAGER")
    items, note = await svc.psych_cases(report.id, admin)
    assert items and note == ""

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
