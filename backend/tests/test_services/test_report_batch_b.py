"""M5 批次 B（口径与健壮性）专项测试。

覆盖：M5-02.2 / 03.5 / 04.1 / 04.2 / 04.3 / 06.4 / 07.1 / 08.5 / 11.5 / 12.2 / 12.3。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import BusinessError, ValidationError
from app.repositories.report_repo import ReportRepository
from app.schemas.report import (
    ComplaintReportInput,
    CustomerReportInput,
    MockReportDataset,
    ReportListOut,
    ReportOut,
)
from app.services import report_service as rs_module
from app.services.report_calculator import (
    calculate_complaint_stats,
    calculate_customer_stats,
    is_special_case,
)
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset
from app.services.report_pdf import generate_report_pdf
from app.utils.report_period import PeriodValidationError, validate_period, week_range


REF_NOW = datetime(2026, 10, 19, 8, 0, 0)  # 参考周期结束后


# ── M5-03.5 特别案例统一口径 ─────────────────────────────

def _complaint(**kw) -> ComplaintReportInput:
    base = dict(ticket_id=99, student_id=1, feedback_type="投诉",
                submitted_at=datetime(2026, 10, 13, 9, 0, 0))
    base.update(kw)
    return ComplaintReportInput(**base)


def test_special_case_requires_high_risk_and_approved():
    # 仅复核通过、非 AI 候选 → 不是特别案例（calculator 旧口径的漏判场景）
    assert is_special_case(_complaint(ai_high_risk=False, review_status="approved")) is False
    # AI 候选但未复核 → 不是
    assert is_special_case(_complaint(ai_high_risk=True, review_status="pending")) is False
    # AI 候选且复核通过 → 是
    assert is_special_case(_complaint(ai_high_risk=True, review_status="approved")) is True


def test_special_case_count_matches_drilldown_criteria():
    """calculator 计数与 drilldown 判定同源：approved 但非 AI 候选不进计数。"""
    ds = build_mock_dataset()
    ds.complaints.append(_complaint(ticket_id=20, ai_high_risk=False, review_status="approved"))
    m = calculate_complaint_stats(ds.complaints, PERIOD_START, PERIOD_END)
    assert m["special_cases"] == 1  # 仍只有 t10（t20 非 AI 候选不计数）


# ── M5-04.1 期末状态周期约束 ─────────────────────────────

def _cust(cid: int, newest: datetime | None, status: str = "NEW") -> CustomerReportInput:
    return CustomerReportInput(
        customer_id=cid, phone=f"139{cid:08d}", name=f"c{cid}", source_channel="WEBSITE_REGISTER",
        first_register_login_at=newest, status_at_period_end=status,
    )


def test_status_overview_excludes_customers_created_after_period_end():
    late = _cust(1, PERIOD_END + timedelta(days=3))          # 周期结束后才新增
    early = _cust(2, PERIOD_START + timedelta(days=1))       # 周期内新增
    undated = _cust(3, None)                                 # 无时间戳，保守计入
    m = calculate_customer_stats([late, early, undated], PERIOD_START, PERIOD_END)
    assert m["status_overview"]["total"] == 2  # late 不计入本期期末


# ── M5-04.2 周期合法性校验 ───────────────────────────────

def test_validate_period_accepts_reference_week():
    validate_period(PERIOD_START, PERIOD_END, now=REF_NOW)  # 不抛即通过


def test_validate_period_accepts_natural_month():
    validate_period(datetime(2026, 10, 1), datetime(2026, 11, 1), now=datetime(2026, 11, 2))


def test_validate_period_rejects_misaligned():
    with pytest.raises(PeriodValidationError):
        validate_period(datetime(2026, 10, 13), datetime(2026, 10, 20), now=REF_NOW)  # 周二起


def test_validate_period_rejects_reverse_or_zero():
    with pytest.raises(PeriodValidationError):
        validate_period(PERIOD_END, PERIOD_START, now=REF_NOW)
    with pytest.raises(PeriodValidationError):
        validate_period(PERIOD_START, PERIOD_START, now=REF_NOW)


def test_validate_period_rejects_overlong_span():
    with pytest.raises(PeriodValidationError):
        validate_period(datetime(2026, 10, 5), datetime(2026, 11, 16), now=datetime(2026, 11, 20))


def test_validate_period_rejects_future_when_checked():
    with pytest.raises(PeriodValidationError):
        validate_period(datetime(2026, 10, 19), datetime(2026, 10, 26), now=REF_NOW, check_future=True)


def test_validate_period_future_exempt_for_mock_reference():
    """mock 参考周期相对真实时钟在「未来」，演示模式豁免未来校验。"""
    validate_period(PERIOD_START, PERIOD_END, now=datetime(2026, 10, 17), check_future=False)


# ── M5-04.3 open_count 周期界定 ──────────────────────────

def test_open_count_excludes_tickets_submitted_after_period_end():
    in_period = _complaint(ticket_id=1, submitted_at=PERIOD_START + timedelta(days=1))
    late = _complaint(ticket_id=2, submitted_at=PERIOD_END + timedelta(days=1))
    m = calculate_complaint_stats([in_period, late], PERIOD_START, PERIOD_END)
    assert m["open_count"] == 1
    assert m["over7_unresolved"] == 0


# ── M5-02.2 mock 提供器支持周期 ──────────────────────────

def test_build_mock_dataset_accepts_period():
    s, e = datetime(2026, 10, 5), datetime(2026, 10, 12)
    ds = build_mock_dataset(s, e)
    assert ds.period_start == s and ds.period_end == e
    # 缺省仍是参考周期
    ds_default = build_mock_dataset()
    assert ds_default.period_start == PERIOD_START and ds_default.period_end == PERIOD_END


# ── M5-07.1 日报/周报指标集拆分（content 侧在 test_report_content 验证） ──

def test_daily_metrics_have_no_week_total_or_departments():
    ds = build_mock_dataset()
    from app.services.report_content import _compute_metrics
    daily = _compute_metrics("daily_report_summary", ds, PERIOD_START, PERIOD_END)
    assert "week_total" not in daily and "departments" not in daily
    weekly = _compute_metrics("weekly_report_summary", ds, PERIOD_START, PERIOD_END)
    assert "week_total" in weekly and "departments" in weekly


# ── M5-08.5 PDF XML 转义 ─────────────────────────────────

def test_pdf_survives_xml_special_chars():
    content = {
        "header": {
            "report_name": "客户<经营>&分析报告", "report_type": "customer_analysis",
            "period_start": "2026-10-12T00:00:00", "period_end": "2026-10-19T00:00:00",
            "generated_at": "2026-10-19T08:00:00", "version": 1, "data_source_status": "mock",
        },
        "summary": "摘要含 <tag> & \"quotes\"",
        "metrics": _customer_metrics(),
        "analysis": "分析含 & 符号 <尖括号>",
        "suggestions": [{"content": "建议含 <b>加粗</b> & 符号"}],
        "data_notes": "口径含 <span>标注</span>",
        "ai_status": "available",
    }
    pdf = generate_report_pdf(content)  # 不抛异常即通过
    assert pdf[:4] == b"%PDF"


def _customer_metrics():
    from app.services.report_calculator import calculate_customer_stats
    ds: MockReportDataset = build_mock_dataset()
    return calculate_customer_stats(ds.customers, PERIOD_START, PERIOD_END)


# ── M5-11.5 下载空内容防护 ───────────────────────────────

class _FakeReport:
    def __init__(self, content):
        self.report_content = content
        self.report_type = "psych_weekly"


class _FakeRepo:
    def __init__(self, report):
        self._report = report

    async def get_by_id(self, report_id):
        return self._report


@pytest.mark.asyncio
async def test_download_empty_content_raises():
    svc = rs_module.ReportService(_FakeRepo(_FakeReport(None)))
    with pytest.raises(ValidationError):
        await svc.download_pdf(1)


@pytest.mark.asyncio
async def test_download_with_content_ok():
    content = {
        "header": {"report_name": "x", "report_type": "psych_weekly", "period_start": "",
                   "period_end": "", "generated_at": "", "version": 1, "data_source_status": "mock"},
        "metrics": {"covered_students": 0, "risk": {"高": 0, "中": 0, "低": 0}},
        "data_notes": "n",
    }
    svc = rs_module.ReportService(_FakeRepo(_FakeReport(content)))
    assert (await svc.download_pdf(1))[:4] == b"%PDF"


# ── M5-12.2 失败态 + 重试 + error_message ────────────────

class _FakeCreateRepo(ReportRepository):
    """可控失败的假仓储：completed 前 fail_times 次抛异常；failed 记录直接落库成功。"""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.saved: list = []

    async def create(self, report):
        self.saved.append(report)
        if report.status == "failed":
            report.id = 1
            return report
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("boom")
        report.id = 2
        return report

    async def next_version(self, report_type, start, end):
        return 1


@pytest.mark.asyncio
async def test_generate_retries_once_and_succeeds():
    repo = _FakeCreateRepo(fail_times=1)
    svc = rs_module.ReportService(repo)
    report = await svc.generate("psych_weekly", None, None, user_id=1)
    assert report.status == "completed"
    assert len(repo.saved) == 2  # 首败 + 重试成功
    assert all(r.status == "completed" for r in repo.saved)


@pytest.mark.asyncio
async def test_generate_persists_failed_record_after_retries():
    repo = _FakeCreateRepo(fail_times=99)
    svc = rs_module.ReportService(repo)
    with pytest.raises(BusinessError):
        await svc.generate("psych_weekly", None, None, user_id=1)
    failed = [r for r in repo.saved if r.status == "failed"]
    assert len(failed) == 1
    assert failed[0].error_message and "boom" in failed[0].error_message


# ── M5-12.3 列表瘦身 ─────────────────────────────────────

def test_report_list_out_excludes_content():
    payload = dict(
        id=1, report_type="psych_weekly", report_title="t",
        report_content={"big": "payload"}, time_range_start=None, time_range_end=None,
        generated_by=1, status="completed", version=1,
        data_source_status="mock", error_message=None, created_at=None,
    )
    slim = ReportListOut(**{k: v for k, v in payload.items() if k != "report_content"})
    assert not hasattr(slim, "report_content")
    full = ReportOut(**payload)
    assert full.report_content == {"big": "payload"}
