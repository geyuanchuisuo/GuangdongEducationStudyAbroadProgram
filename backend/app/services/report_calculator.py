"""M5 智能报告模块 — 确定性指标计算器（阶段 2）

程序负责所有数字与规则判断，禁止在计算器中调用 AI。
计算器只接受统一报告输入（app/schemas/report.py），不直接查询数据库。
"""
from datetime import date, datetime, timedelta

from app.schemas.report import (
    ComplaintReportInput,
    CustomerReportInput,
    EmployeeDailyReportInput,
    EmployeeInput,
    PsychReportInput,
)

# 客户状态分类（与接口契约 §0.5 一致）
INTENT_STATUSES = {"NEW", "FOLLOWING", "STRONG"}
CONVERTED_STATUSES = {"SIGNED", "ENROLLED"}
LOST_STATUS = "LOST"

SEVEN_DAYS = timedelta(hours=7 * 24)


# ── 通用工具 ──────────────────────────────────────────────

def is_special_case(t: ComplaintReportInput) -> bool:
    """特别案例统一口径（M5-03.5）：AI 高风险候选 且 人工复核通过（approved）。

    calculator 与 drilldown 共用本判定，两处不再各写一套。
    """
    return t.ai_high_risk and t.review_status == "approved"


def customer_newest_time(c: CustomerReportInput) -> datetime | None:
    """客户新增时间 = 首次注册登录 / 首次员工提交 两者更早者。"""
    times = [t for t in (c.first_register_login_at, c.first_employee_submit_at) if t is not None]
    return min(times) if times else None


def dedup_customers_by_phone(customers: list[CustomerReportInput]) -> list[CustomerReportInput]:
    """按手机号去重，保留最早新增时间的一条（与口径一致）。"""
    best: dict[str, CustomerReportInput] = {}
    for c in customers:
        t = customer_newest_time(c)
        cur = best.get(c.phone)
        if cur is None or (t is not None and (customer_newest_time(cur) is None or t < customer_newest_time(cur))):
            best[c.phone] = c
    return list(best.values())


# ── 客户经营分析 ──────────────────────────────────────────

def calculate_customer_stats(
    customers: list[CustomerReportInput], period_start: datetime, period_end: datetime
) -> dict:
    uniq = dedup_customers_by_phone(customers)

    # 期末状态总览（M5-04.1 周期约束：仅统计周期结束前已存在的客户；
    # 新增时间晚于 period_end 的客户属于未来周期，不计入本期期末）
    existing = [
        c for c in uniq
        if (t := customer_newest_time(c)) is None or t < period_end
    ]
    status_counts = {s: 0 for s in ("NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST")}
    for c in existing:
        status_counts[c.status_at_period_end] += 1
    intent = sum(status_counts[s] for s in INTENT_STATUSES)
    converted = sum(status_counts[s] for s in CONVERTED_STATUSES)
    lost = status_counts[LOST_STATUS]

    # 本期新增（新增时间在周期内，已按手机号去重）
    new_customers = [
        c for c in uniq
        if (t := customer_newest_time(c)) is not None and period_start <= t < period_end
    ]
    new_outcomes = {
        "intent": sum(1 for c in new_customers if c.status_at_period_end in INTENT_STATUSES),
        "signed": sum(1 for c in new_customers if c.status_at_period_end == "SIGNED"),
        "enrolled": sum(1 for c in new_customers if c.status_at_period_end == "ENROLLED"),
        "lost": sum(1 for c in new_customers if c.status_at_period_end == "LOST"),
    }

    # 项目画像：分母 = 全部期末意向客户（同 M5-04.1 仅计周期结束前已存在者）；
    # None 归"信息不足"（未完成研判）
    intent_customers = [c for c in existing if c.status_at_period_end in INTENT_STATUSES]
    profiles = {}
    for attr in ("sg_conclusion", "de_conclusion"):
        counts = {"符合": 0, "不符合": 0, "信息不足": 0}
        for c in intent_customers:
            v = getattr(c, attr)
            counts["信息不足" if v is None else v] += 1
        profiles[attr] = counts

    return {
        "status_overview": {
            **status_counts,
            "total": len(existing),
            "intent": intent,
            "converted": converted,
            "lost": lost,
        },
        "new_this_period": len(new_customers),
        "new_outcomes": new_outcomes,
        "profiles": profiles,
    }


# ── 员工日报 / 周报 ───────────────────────────────────────

def _submitted_map(reports: list[EmployeeDailyReportInput]) -> dict[tuple[int, date], bool]:
    """有效日报按 (员工, 业务日期) 去重。"""
    m: dict[tuple[int, date], bool] = {}
    for r in reports:
        if r.is_valid:
            m[(r.employee_id, r.report_date)] = True
    return m


def _weekdays_in_period(period_start: datetime, period_end: datetime) -> list[date]:
    """周期内的周一至周五日期列表。"""
    days: list[date] = []
    d = period_start.date()
    while d < period_end.date():
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def calculate_daily_submission(
    employees: list[EmployeeInput],
    reports: list[EmployeeDailyReportInput],
    period_start: datetime,
    period_end: datetime,
) -> dict:
    active = [e for e in employees if e.employment_status == "active"]
    submitted = _submitted_map(reports)
    days = []
    for d in _weekdays_in_period(period_start, period_end):
        n = sum(1 for e in active if (e.employee_id, d) in submitted)
        days.append({
            "date": d.isoformat(),
            "should_submit": len(active),
            "submitted": n,
            "missing": len(active) - n,
        })
    return {"days": days}


def calculate_weekly_submission(
    employees: list[EmployeeInput],
    reports: list[EmployeeDailyReportInput],
    period_start: datetime,
    period_end: datetime,
) -> dict:
    active = [e for e in employees if e.employment_status == "active"]
    submitted = _submitted_map(reports)
    weekdays = _weekdays_in_period(period_start, period_end)

    days = []
    for d in weekdays:
        n = sum(1 for e in active if (e.employee_id, d) in submitted)
        days.append({
            "date": d.isoformat(),
            "should_submit": len(active),
            "submitted": n,
            "missing": len(active) - n,
        })

    total_should = len(active) * len(weekdays)
    total_submitted = sum(day["submitted"] for day in days)

    dept_ids: dict[str, list[int]] = {}
    for e in active:
        dept_ids.setdefault(e.department, []).append(e.employee_id)
    departments = {}
    for dept, eids in dept_ids.items():
        should = len(eids) * len(weekdays)
        sub = sum(1 for eid in eids for d in weekdays if (eid, d) in submitted)
        departments[dept] = {"should_submit": should, "submitted": sub, "missing": should - sub}

    return {
        "days": days,
        "week_total": {
            "should_submit": total_should,
            "submitted": total_submitted,
            "missing": total_should - total_submitted,
        },
        "departments": departments,
    }


# ── 心理周报 ──────────────────────────────────────────────

def calculate_psych_stats(
    records: list[PsychReportInput], period_start: datetime, period_end: datetime
) -> dict:
    in_period = [r for r in records if period_start <= r.record_at < period_end]
    # 同一学生多条记录按学生去重，取最新一条记录的风险等级
    latest: dict[int, PsychReportInput] = {}
    for r in in_period:
        cur = latest.get(r.student_id)
        if cur is None or r.record_at >= cur.record_at:
            latest[r.student_id] = r

    risk = {"高": 0, "中": 0, "低": 0}
    for r in latest.values():
        if r.risk_level in risk:
            risk[r.risk_level] += 1
    return {"covered_students": len(latest), "risk": risk}


# ── 投诉周报 ──────────────────────────────────────────────

def calculate_complaint_stats(
    complaints: list[ComplaintReportInput], period_start: datetime, period_end: datetime
) -> dict:
    complaints = [t for t in complaints if t.feedback_type == "投诉"]

    new_count = sum(1 for t in complaints if period_start <= t.submitted_at < period_end)
    resolved_in_period = sum(
        1 for t in complaints
        if t.resolved_at is not None and period_start <= t.resolved_at < period_end
    )
    # 期末未解决（M5-04.3 周期界定：仅统计周期结束前已提交、截止时仍 open 的工单）
    open_count = sum(
        1 for t in complaints
        if t.status == "open" and t.submitted_at < period_end
    )
    # 超过 7×24h 仍未解决（严格大于，恰好 7 天不算）
    over7 = sum(
        1 for t in complaints
        if t.status == "open" and t.submitted_at < period_end
        and (period_end - t.submitted_at) > SEVEN_DAYS
    )

    responded = [t for t in complaints if t.first_response_at is not None]
    not_responded = sum(1 for t in complaints if t.first_response_at is None)
    durations = [(t.first_response_at - t.submitted_at).total_seconds() for t in responded]
    avg_seconds = sum(durations) / len(durations) if durations else None
    max_seconds = max(durations) if durations else None

    satisfaction = {"满意": 0, "不满意": 0, "未评价": 0}
    for t in complaints:
        satisfaction[t.satisfaction] += 1

    # 特别案例（M5-03.5 统一口径）：AI 高风险候选且已复核通过
    special_cases = sum(1 for t in complaints if is_special_case(t))

    return {
        "new_count": new_count,
        "resolved_in_period": resolved_in_period,
        "open_count": open_count,
        "over7_unresolved": over7,
        "first_response_count": len(responded),
        "not_responded_count": not_responded,
        "avg_first_response_seconds": avg_seconds,
        "max_first_response_seconds": max_seconds,
        "satisfaction": satisfaction,
        "special_cases": special_cases,
    }
