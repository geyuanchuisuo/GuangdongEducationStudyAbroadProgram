"""M5 智能报告模块 — 阶段6 PDF 汇总导出验证。"""
import asyncio

from app.services.report_ai_service import ReportAIService
from app.services.report_content import REPORT_TYPE_NAMES, build_report_content
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset
from app.services.report_pdf import generate_report_pdf


def _full_content(report_type: str) -> dict:
    ds = build_mock_dataset()
    content = build_report_content(report_type, ds, PERIOD_START, PERIOD_END, 1, PERIOD_END)
    analysis = asyncio.run(ReportAIService().analyze(report_type, content["metrics"]))
    if analysis:
        content.update(analysis)
        content["ai_status"] = "available"
    else:
        content["ai_status"] = "unavailable"
    return content


def test_pdf_generates_for_all_types():
    for rt in REPORT_TYPE_NAMES:
        pdf = generate_report_pdf(_full_content(rt))
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000
