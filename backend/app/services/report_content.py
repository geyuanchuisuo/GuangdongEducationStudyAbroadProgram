"""M5 智能报告模块 — 统一报告内容结构（阶段 3）

报告内容统一分为：报告头、本期摘要、核心指标、趋势/对比、业务分析、建议事项、口径说明。
摘要 / 趋势 / 分析 / 建议由阶段 5 AI 填充；本阶段只写入确定性指标与口径说明。
"""
from datetime import datetime

from app.schemas.report import MockReportDataset
from app.services.report_calculator import (
    calculate_complaint_stats,
    calculate_customer_stats,
    calculate_psych_stats,
    calculate_weekly_submission,
)

REPORT_TYPE_NAMES = {
    "customer_analysis": "客户经营分析报告",
    "daily_report_summary": "员工日报汇总",
    "weekly_report_summary": "员工周报汇总",
    "psych_weekly": "学生心理健康周报",
    "complaint_weekly": "投诉处理周报",
}

DATA_NOTES = {
    "customer_analysis": "口径：期末状态取周期结束时状态；本期新增按手机号去重、取最早新增时间；"
                         "画像分母为全部期末意向客户，无有效研判归信息不足；历史画像按当前最新研判重算。",
    "daily_report_summary": "口径：应提交范围为在职员工、周一至周五；同一员工同一日报日期最多计一次有效提交；"
                            "补交归回原日期；周末不计应交/未交。",
    "weekly_report_summary": "口径：同日报；部门归属按生成时员工部门汇总；全周人次为各工作日应交/已交/未交之和。",
    "psych_weekly": "口径：覆盖学生为本周期有心理记录的学生、按学生ID去重；风险结果沿用学生模块识别结果；"
                    "无记录不计比例、不视为正常。",
    "complaint_weekly": "口径：统计对象为 feedback_type=投诉；首次响应时长=首次响应-提交，未响应不计入平均/最长；"
                        "长期未解决=截止未解决且提交至截止超7×24小时；特别案例仅统计已复核通过。",
}


def _compute_metrics(report_type: str, ds: MockReportDataset, start: datetime, end: datetime) -> dict:
    if report_type == "customer_analysis":
        return calculate_customer_stats(ds.customers, start, end)
    if report_type in ("daily_report_summary", "weekly_report_summary"):
        return calculate_weekly_submission(ds.employees, ds.daily_reports, start, end)
    if report_type == "psych_weekly":
        return calculate_psych_stats(ds.psych_records, start, end)
    if report_type == "complaint_weekly":
        return calculate_complaint_stats(ds.complaints, start, end)
    raise ValueError(f"未知报告类型: {report_type}")


def build_report_content(
    report_type: str,
    ds: MockReportDataset,
    period_start: datetime,
    period_end: datetime,
    version: int,
    generated_at: datetime,
) -> dict:
    """组装统一报告内容。summary / trend / analysis / suggestions 由阶段 5 AI 填充。"""
    data_source_status = "production" if not ds.is_mock else "mock"
    return {
        "header": {
            "report_name": REPORT_TYPE_NAMES[report_type],
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "data_updated_at": ds.data_updated_at.isoformat(),
            "generated_at": generated_at.isoformat(),
            "version": version,
            "data_source_status": data_source_status,
        },
        "summary": None,
        "metrics": _compute_metrics(report_type, ds, period_start, period_end),
        "trend": None,
        "analysis": None,
        "suggestions": None,
        "data_notes": DATA_NOTES[report_type],
    }
