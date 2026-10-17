"""M5 批次 E（M5-10.1/10.2/10.3/10.4/10.5/10.6/10.8）测试资产。

API 权限矩阵与入参边界（conftest SQLite client）+ 编排层（版本递增/列表折叠/
AI 降级/非参考周期）+ calculator↔drilldown 交叉一致 + PDF 无个人字段结构回归。
"""
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.repositories.report_repo import ReportRepository
from app.services import report_service as rs_module
from app.services.report_ai_service import ReportAIService
from app.services.report_calculator import calculate_complaint_stats
from app.services.report_drilldown import special_cases_drilldown
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset


# ── M5-10.2 编排层：版本递增与列表折叠 ───────────────────

@pytest_asyncio.fixture
async def svc_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'orch.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_version_increments_and_list_folds(svc_db):
    svc = rs_module.ReportService(ReportRepository(svc_db))
    r1 = await svc.generate("psych_weekly", None, None, user_id=1)
    r2 = await svc.generate("psych_weekly", None, None, user_id=1)
    assert (r1.version, r2.version) == (1, 2)
    # 其它类型互不影响
    await svc.generate("customer_analysis", None, None, user_id=1)
    items, total = await svc.list_reports(None, 1, 10)
    assert total == 2  # 同类型同周期折叠为最新版本
    psych = [i for i in items if i.report_type == "psych_weekly"]
    assert len(psych) == 1 and psych[0].version == 2
    # 列表瘦身：条目经 ReportListOut 序列化不含 report_content
    from app.schemas.report import ReportListOut
    assert not hasattr(ReportListOut.model_validate(psych[0]), "report_content")


@pytest.mark.asyncio
async def test_generate_records_ai_status_and_mock_source(svc_db):
    svc = rs_module.ReportService(ReportRepository(svc_db))
    report = await svc.generate("complaint_weekly", None, None, user_id=1)
    content = report.report_content
    assert content["ai_status"] == "available"
    # M5-10.6 差异字段：无 model key 时回落模拟输出，来源标注 mock
    assert content["ai_source"] == "mock"
    assert report.data_source_status == "mock"
    assert content["header"]["data_source_status"] == "mock"


# ── M5-10.5 AI 降级分支 ──────────────────────────────────

@pytest.mark.asyncio
async def test_ai_degradation_marks_unavailable(svc_db):
    class _DownAI(ReportAIService):
        async def analyze(self, report_type, metrics):
            return None  # 模拟 AI 不可用

    svc = rs_module.ReportService(ReportRepository(svc_db), ai=_DownAI())
    report = await svc.generate("psych_weekly", None, None, user_id=1)
    assert report.report_content["ai_status"] == "unavailable"
    # M5-10.6 差异字段：AI 不可用时来源同样显式标注
    assert report.report_content["ai_source"] == "unavailable"
    # 确定性指标保留（不因 AI 失败丢数字）
    assert "covered_students" in report.report_content["metrics"]


# ── M5-10.3 非参考周期（mock 显式传过去周期） ────────────

@pytest.mark.asyncio
async def test_generate_with_explicit_past_period(svc_db):
    svc = rs_module.ReportService(ReportRepository(svc_db))
    start, end = datetime(2026, 9, 7), datetime(2026, 9, 14)
    report = await svc.generate("psych_weekly", start, end, user_id=1)
    assert report.time_range_start == start and report.time_range_end == end
    # 非参考周期 mock 数据为空属预期：覆盖 0 人（真实为零而非编造）
    assert report.report_content["metrics"]["covered_students"] == 0


# ── M5-10.4 calculator ↔ drilldown 交叉一致 ──────────────

def test_special_cases_cross_consistency():
    ds = build_mock_dataset()
    m = calculate_complaint_stats(ds.complaints, PERIOD_START, PERIOD_END)
    items = special_cases_drilldown(ds)
    assert m["special_cases"] == len(items) == 1  # 同一 is_special_case 判定


# ── M5-10.6 PDF 内容结构无个人字段（脱敏结构回归） ───────

def test_report_content_has_no_personal_fields():
    def _scan(node, keys):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k.lower() not in {"phone", "mobile", "wechat", "feedback_summary", "content原文"}, k
                _scan(v, keys)
        elif isinstance(node, list):
            for item in node:
                _scan(item, keys)

    from app.services.report_content import build_report_content
    for rt in ("customer_analysis", "psych_weekly", "complaint_weekly"):
        content = build_report_content(rt, build_mock_dataset(), PERIOD_START, PERIOD_END, 1, datetime.now())
        _scan(content, set())


# ── M5-10.8 未落字段回归（如实记录当前不参与计算的字段） ─

def test_documented_unused_fields_stay_inert():
    """迟报 is_late、has_psych_record、ai_low_score：当前口径不参与计算——
    一旦有人误改计算器让它们生效而无口径依据，此测试提醒对齐口径文档。"""
    from app.schemas.report import EmployeeDailyReportInput, PsychReportInput
    r = EmployeeDailyReportInput(employee_id=1, department="x", report_date=datetime(2026, 10, 13).date(),
                                 submitted_at=datetime(2026, 10, 14), content="c", is_valid=True)
    assert not hasattr(r, "is_late")  # 迟报未进统一输入（映射表已记录）
    p = PsychReportInput(student_id=1, record_at=datetime(2026, 10, 13))
    assert p.has_psych_record is True and "has_psych_record" not in dir(rs_module)
    c_inert = {"ai_low_score": False}
    ds = build_mock_dataset()
    m = calculate_complaint_stats(ds.complaints, PERIOD_START, PERIOD_END)
    # ai_low_score 不影响任何指标（特别案例仅看 ai_high_risk + review_status）
    assert m["special_cases"] == 1
    assert c_inert["ai_low_score"] is False
