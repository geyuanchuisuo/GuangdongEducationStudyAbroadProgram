"""M5 智能报告模块 — 阶段5 AI 分析验证。"""
import asyncio

from app.services.report_ai_service import ReportAIService, _mock_analysis, _validate
from app.services.report_content import REPORT_TYPE_NAMES, build_report_content
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset


def _metrics(report_type: str) -> dict:
    return build_report_content(
        report_type, build_mock_dataset(), PERIOD_START, PERIOD_END, 1, PERIOD_END
    )["metrics"]


def test_mock_analysis_is_valid_for_all_types():
    for rt in REPORT_TYPE_NAMES:
        analysis = _mock_analysis(rt, _metrics(rt))
        assert _validate(analysis) is not None  # 结构校验通过


def test_validate_rejects_malformed():
    assert _validate(None) is None
    assert _validate({}) is None
    assert _validate({"summary": "x", "analysis": "y"}) is None  # 缺 trend/suggestions
    assert _validate({"summary": 1, "trend": None, "analysis": "y", "suggestions": []}) is None


def test_mock_analysis_uses_program_metrics():
    m = _metrics("customer_analysis")
    analysis = _mock_analysis("customer_analysis", m)
    # 数字来自程序计算，不自行计算
    assert f"本期新增客户 {m['new_this_period']} 名" in analysis["summary"]
    assert f"期末意向 {m['status_overview']['intent']} 名" in analysis["summary"]


def test_analyze_returns_valid_or_none():
    svc = ReportAIService()
    for rt in REPORT_TYPE_NAMES:
        result = asyncio.run(svc.analyze(rt, _metrics(rt)))
        assert result is not None
        assert set(result.keys()) == {"summary", "trend", "analysis", "suggestions"}
