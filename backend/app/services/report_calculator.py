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
    """特别案例统一口径（v6.11.0 §2.6）：一期无人工复核，由 AI 判定。

    仅「已有成功 AI 分析 且 AI 判为高风险」的工单算特别案例；
    待分析/失败工单不参与 AI 类指标，也不得被当特别案例。
    """
    return t.analysis_status == "analyzed" and t.ai_high_risk


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
    """客户经营指标（v6.11.0 口径）。

    - 期末状态：只能用周期末的真实状态；适配器拿不到历史时点时置 None，
      此时**所有依赖状态的指标标「数据不可得」**，不用当前值冒充（§2.3/§六）。
    - 新增客户：只依赖时间，始终可算。
    - 画像：四类独立（符合/部分符合/不符合/信息不足）；**分母只计有有效研判的意向客户**，
      无研判不补值、不归入「信息不足」（§2.3）。
    """
    uniq = dedup_customers_by_phone(customers)

    # 周期末已存在的客户（新增时间晚于 period_end 的属于未来周期）
    existing = [
        c for c in uniq
        if (t := customer_newest_time(c)) is None or t < period_end
    ]

    # 本期新增（仅依赖时间 → 不受期末状态可得性影响）
    new_customers = [
        c for c in uniq
        if (t := customer_newest_time(c)) is not None and period_start <= t < period_end
    ]

    # 期末状态可得性：全部期末客户都有状态值才算可得
    status_available = bool(existing) and all(c.status_at_period_end is not None for c in existing)

    if status_available:
        status_counts = {s: 0 for s in ("NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST")}
        for c in existing:
            status_counts[c.status_at_period_end] += 1
        intent = sum(status_counts[s] for s in INTENT_STATUSES)
        converted = sum(status_counts[s] for s in CONVERTED_STATUSES)
        lost = status_counts[LOST_STATUS]
        status_overview = {
            **status_counts,
            "total": len(existing),
            "intent": intent,
            "converted": converted,
            "lost": lost,
        }
        new_outcomes = {
            "intent": sum(1 for c in new_customers if c.status_at_period_end in INTENT_STATUSES),
            "signed": sum(1 for c in new_customers if c.status_at_period_end == "SIGNED"),
            "enrolled": sum(1 for c in new_customers if c.status_at_period_end == "ENROLLED"),
            "lost": sum(1 for c in new_customers if c.status_at_period_end == "LOST"),
        }
        # 四类画像：分母 = 周期末有有效研判的意向客户（无研判不计入、不补值）
        intent_customers = [c for c in existing if c.status_at_period_end in INTENT_STATUSES]
        profiles: dict[str, dict] = {}
        profile_denominator: dict[str, int] = {}
        for attr in ("sg_conclusion", "de_conclusion"):
            counted = [c for c in intent_customers if getattr(c, attr) is not None]
            counts = {"符合": 0, "部分符合": 0, "不符合": 0, "信息不足": 0}
            for c in counted:
                counts[getattr(c, attr)] += 1
            profiles[attr] = counts
            profile_denominator[attr] = len(counted)
        profiles_availability = "ok" if any(v > 0 for v in profile_denominator.values()) else "no_data"
    else:
        status_overview = None
        new_outcomes = None
        profiles = {attr: None for attr in ("sg_conclusion", "de_conclusion")}
        profile_denominator = {attr: None for attr in ("sg_conclusion", "de_conclusion")}
        profiles_availability = "unavailable"

    return {
        "status_overview": status_overview,
        "new_this_period": len(new_customers),
        "new_outcomes": new_outcomes,
        "profiles": profiles,
        "profile_denominator": profile_denominator,
        "availability": {
            "status": "ok" if status_available else "unavailable",
            "profiles": profiles_availability,
        },
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
    """投诉周报指标（v6.11.0 §2.6 口径）。

    - 工单总量：周期内提交的全部工单（含待分析），单独呈现待分析数量；
    - AI 类指标（低满意候选/高风险/特别案例/AI 摘要）只对**已有成功分析**的工单生效，
      待分析/失败工单不纳入，也不得冒充已分析；
    - 投诉分类：来源须为学生所选或 AI 分类，且类型=投诉（建议/咨询不计入）；
    - 满意度只取学生明确评价，「未评价」不推测；
    - 时效为事实字段（首次响应/解决时间由 M4 流程记录），不参与 AI 推断。
    """
    in_period = [t for t in complaints if period_start <= t.submitted_at < period_end]
    analyzed = [t for t in in_period if t.analysis_status == "analyzed"]
    pending_analysis = sum(1 for t in in_period if t.analysis_status != "analyzed")

    def _is_complaint(t: ComplaintReportInput) -> bool:
        return t.feedback_type == "投诉" and t.category_source in ("student", "ai")

    # 本期投诉（类型来源可信且已分析）：分类/满意度/AI 类指标的分母
    complaints_in_period = [t for t in analyzed if _is_complaint(t)]
    # 期末未解决与超时按「周期结束前已提交、截止时仍 open」统计（含跨期历史工单）
    complaints_to_end = [
        t for t in complaints
        if _is_complaint(t) and t.analysis_status == "analyzed" and t.submitted_at < period_end
    ]

    new_count = len(complaints_in_period)
    resolved_in_period = sum(
        1 for t in complaints_to_end
        if t.resolved_at is not None and period_start <= t.resolved_at < period_end
    )
    open_count = sum(1 for t in complaints_to_end if t.status == "open")
    # 超过 7×24h 仍未解决（严格大于，恰好 7 天不算）
    over7 = sum(
        1 for t in complaints_to_end
        if t.status == "open" and (period_end - t.submitted_at) > SEVEN_DAYS
    )

    responded = [t for t in complaints_in_period if t.first_response_at is not None]
    not_responded = sum(1 for t in complaints_in_period if t.first_response_at is None)
    durations = [(t.first_response_at - t.submitted_at).total_seconds() for t in responded]
    avg_seconds = sum(durations) / len(durations) if durations else None
    max_seconds = max(durations) if durations else None

    satisfaction = {"满意": 0, "不满意": 0, "未评价": 0}
    for t in complaints_in_period:
        satisfaction[t.satisfaction] += 1

    special_cases = sum(1 for t in complaints_in_period if is_special_case(t))
    low_satisfaction = sum(1 for t in complaints_in_period if t.ai_low_score)
    high_risk = sum(1 for t in complaints_in_period if t.ai_high_risk)

    if not in_period:
        ai_availability = "no_data"
    elif pending_analysis == 0:
        ai_availability = "ok"
    elif analyzed:
        ai_availability = "partial"
    else:
        ai_availability = "unavailable"

    return {
        # 工单总量与待分析（待分析只入总量，不入 AI 指标）
        "orders_total": len(in_period),
        "pending_analysis": pending_analysis,
        "analyzed_count": len(analyzed),
        "new_count": new_count,
        "resolved_in_period": resolved_in_period,
        "open_count": open_count,
        "over7_unresolved": over7,
        "first_response_count": len(responded),
        "not_responded_count": not_responded,
        "avg_first_response_seconds": avg_seconds,
        "max_first_response_seconds": max_seconds,
        "satisfaction": satisfaction,
        "low_satisfaction_candidates": low_satisfaction,
        "high_risk_candidates": high_risk,
        "special_cases": special_cases,
        "availability": {
            "ai_analysis": ai_availability,
            # 首次响应时间由 M4 记录；一条都没有时无法区分「全都未响应」与「字段未落库」
            "timeliness": "ok" if responded else "unknown",
            "satisfaction": "ok" if complaints_in_period else "no_data",
        },
    }
