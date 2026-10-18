"""M5 智能报告模块 — 阶段2 确定性指标计算器验证

全部预期值均为按口径人工核对，用于锁定计算器行为（程序算数字）。
"""
from datetime import datetime

from app.services.report_calculator import (
    calculate_complaint_stats,
    calculate_customer_stats,
    calculate_daily_submission,
    calculate_psych_stats,
    calculate_weekly_submission,
)
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset
from app.utils.report_period import month_range, week_range

# ── 周期工具 ──────────────────────────────────────────────

def test_week_range_monday():
    # 周三 anchor -> 所在周周一至下周一
    start, end = week_range(datetime(2026, 10, 14, 15, 30))
    assert start == datetime(2026, 10, 12, 0, 0, 0)
    assert end == datetime(2026, 10, 19, 0, 0, 0)


def test_week_range_sunday_is_end_of_week():
    # 周日 anchor 仍属本周
    start, end = week_range(datetime(2026, 10, 18, 23, 0))
    assert start == datetime(2026, 10, 12, 0, 0, 0)
    assert end == datetime(2026, 10, 19, 0, 0, 0)


def test_month_range():
    start, end = month_range(datetime(2026, 10, 14))
    assert start == datetime(2026, 10, 1, 0, 0, 0)
    assert end == datetime(2026, 11, 1, 0, 0, 0)


def test_month_range_december():
    start, end = month_range(datetime(2026, 12, 31))
    assert start == datetime(2026, 12, 1, 0, 0, 0)
    assert end == datetime(2027, 1, 1, 0, 0, 0)


# ── 客户经营分析 ──────────────────────────────────────────

def test_customer_stats():
    ds = build_mock_dataset()
    r = calculate_customer_stats(ds.customers, PERIOD_START, PERIOD_END)

    ov = r["status_overview"]
    assert ov["total"] == 13  # 14 条记录去重为 13 个唯一客户
    assert ov["NEW"] == 3
    assert ov["FOLLOWING"] == 2
    assert ov["STRONG"] == 1
    assert ov["SIGNED"] == 2
    assert ov["ENROLLED"] == 2
    assert ov["LOST"] == 3
    assert ov["intent"] == 6   # NEW+FOLLOWING+STRONG
    assert ov["converted"] == 4  # SIGNED+ENROLLED
    assert ov["lost"] == 3

    assert r["new_this_period"] == 9
    assert r["new_outcomes"] == {"intent": 5, "signed": 1, "enrolled": 1, "lost": 2}

    # v6.11.0：画像四类独立；分母只计周期末有有效研判的意向客户（无研判不补值）
    assert r["profiles"]["sg_conclusion"] == {"符合": 3, "部分符合": 1, "不符合": 1, "信息不足": 1}
    assert r["profiles"]["de_conclusion"] == {"符合": 3, "部分符合": 1, "不符合": 1, "信息不足": 1}
    assert r["profile_denominator"] == {"sg_conclusion": 6, "de_conclusion": 6}
    assert r["availability"] == {"status": "ok", "profiles": "ok"}


# ── 员工日报 / 周报 ───────────────────────────────────────

def test_daily_submission():
    ds = build_mock_dataset()
    r = calculate_daily_submission(ds.employees, ds.daily_reports, PERIOD_START, PERIOD_END)

    days = r["days"]
    assert len(days) == 5  # 仅周一至周五
    # 应交均为 5 人
    assert all(d["should_submit"] == 5 for d in days)
    submitted = [d["submitted"] for d in days]
    assert submitted == [4, 4, 5, 3, 4]
    missing = [d["missing"] for d in days]
    assert missing == [1, 1, 0, 2, 1]


def test_weekly_submission():
    ds = build_mock_dataset()
    r = calculate_weekly_submission(ds.employees, ds.daily_reports, PERIOD_START, PERIOD_END)

    assert r["week_total"] == {"should_submit": 25, "submitted": 20, "missing": 5}
    # 分部门：咨询部(e1,e2)、教务部(e3,e4)、市场部(e5)
    assert r["departments"]["咨询部"] == {"should_submit": 10, "submitted": 8, "missing": 2}
    assert r["departments"]["教务部"] == {"should_submit": 10, "submitted": 8, "missing": 2}
    assert r["departments"]["市场部"] == {"should_submit": 5, "submitted": 4, "missing": 1}


# ── 心理周报 ──────────────────────────────────────────────

def test_psych_stats():
    ds = build_mock_dataset()
    r = calculate_psych_stats(ds.psych_records, PERIOD_START, PERIOD_END)

    assert r["covered_students"] == 4  # s2 两条记录去重
    assert r["risk"] == {"高": 2, "中": 1, "低": 1}


# ── 投诉周报 ──────────────────────────────────────────────

def test_complaint_stats():
    ds = build_mock_dataset()
    r = calculate_complaint_stats(ds.complaints, PERIOD_START, PERIOD_END)

    # v6.11.0：工单总量/待分析单列；投诉与 AI 指标只算「已分析 + 来源可信」
    assert r["orders_total"] == 9           # 周期内工单（t3/t8 早于周期起点，不计本期）
    assert r["pending_analysis"] == 1       # t11 待分析
    assert r["analyzed_count"] == 8
    assert r["new_count"] == 6              # t1/t2/t4/t7/t9/t10
    assert r["resolved_in_period"] == 2     # t1(10-14)、t7(10-16)
    assert r["open_count"] == 6             # 含跨期仍未解决的 t3/t8
    assert r["over7_unresolved"] == 2       # t3(10-06)、t8(10-11 23:59)，恰好 7 天不算
    assert r["first_response_count"] == 4   # 本期投诉中 t1/t7/t9/t10
    assert r["not_responded_count"] == 2    # t2/t4
    assert r["avg_first_response_seconds"] == 4500.0   # (7200+3600+3600+3600)/4
    assert r["max_first_response_seconds"] == 7200.0
    assert r["satisfaction"] == {"满意": 1, "不满意": 1, "未评价": 4}
    # v6.11.0：一期 AI 判定（无需人工复核）→ t9/t10 都是特别案例
    assert r["special_cases"] == 2
    assert r["low_satisfaction_candidates"] == 1
    assert r["high_risk_candidates"] == 2
    assert r["availability"]["ai_analysis"] == "partial"  # 有 1 条待分析
