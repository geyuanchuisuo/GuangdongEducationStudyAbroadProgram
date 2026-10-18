"""M5 智能报告模块 — 阶段3 统一报告内容结构验证。"""
from datetime import datetime

from app.services.report_content import REPORT_TYPE_NAMES, build_report_content
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset

GEN_AT = datetime(2026, 10, 19, 8, 0, 0)


def _build(report_type: str) -> dict:
    return build_report_content(report_type, build_mock_dataset(), PERIOD_START, PERIOD_END, 1, GEN_AT)


def test_header_and_sections():
    content = _build("customer_analysis")
    h = content["header"]
    assert h["report_name"] == "客户经营分析报告"
    assert h["report_type"] == "customer_analysis"
    assert h["period_start"] == PERIOD_START.isoformat()
    assert h["period_end"] == PERIOD_END.isoformat()
    assert h["version"] == 1
    assert h["data_source_status"] == "mock"  # 模拟数据

    # 未接 AI 前，摘要/趋势/分析/建议均为空
    assert content["summary"] is None
    assert content["trend"] is None
    assert content["analysis"] is None
    assert content["suggestions"] is None
    assert isinstance(content["data_notes"], str)


def test_all_report_types_build():
    for rt in REPORT_TYPE_NAMES:
        content = _build(rt)
        assert content["header"]["report_type"] == rt
        assert content["metrics"]  # 每个类型都有确定性指标


def test_customer_metrics():
    content = _build("customer_analysis")
    m = content["metrics"]
    assert m["status_overview"]["total"] == 13
    assert m["new_this_period"] == 9
    # v6.11.0：四类画像（mock 里已含「部分符合」样本）
    assert m["profiles"]["sg_conclusion"] == {"符合": 3, "部分符合": 1, "不符合": 1, "信息不足": 1}
    assert m["profile_denominator"]["sg_conclusion"] == 6


def test_daily_and_weekly_split_submission_stats():
    """M5-07.1 日报与周报拆开：日报只有按日明细，周报才有全周人次与部门汇总。"""
    daily = _build("daily_report_summary")["metrics"]
    weekly = _build("weekly_report_summary")["metrics"]

    # 日报：仅按日应交/已交/未交，不含全周人次与部门
    assert len(daily["days"]) == 5
    assert "week_total" not in daily
    assert "departments" not in daily
    assert sum(d["submitted"] for d in daily["days"]) == 20

    # 周报：含每日明细 + 全周人次 + 部门汇总
    assert len(weekly["days"]) == 5
    assert weekly["week_total"]["submitted"] == 20
    assert set(weekly["departments"]) == {"咨询部", "教务部", "市场部"}


def test_psych_metrics():
    m = _build("psych_weekly")["metrics"]
    assert m["covered_students"] == 4
    assert m["risk"] == {"高": 2, "中": 1, "低": 1}


def test_complaint_metrics():
    m = _build("complaint_weekly")["metrics"]
    assert m["new_count"] == 6
    assert m["over7_unresolved"] == 2
    # v6.11.0：一期 AI 判定（无需人工复核）→ t9/t10 都是特别案例
    assert m["special_cases"] == 2
    # 待分析工单只入工单总量，不进投诉/AI 指标
    assert m["orders_total"] == 9
    assert m["pending_analysis"] == 1
    assert m["analyzed_count"] == 8


def test_version_reflected_in_header():
    c1 = build_report_content("psych_weekly", build_mock_dataset(), PERIOD_START, PERIOD_END, 1, GEN_AT)
    c2 = build_report_content("psych_weekly", build_mock_dataset(), PERIOD_START, PERIOD_END, 2, GEN_AT)
    assert c1["header"]["version"] == 1
    assert c2["header"]["version"] == 2
