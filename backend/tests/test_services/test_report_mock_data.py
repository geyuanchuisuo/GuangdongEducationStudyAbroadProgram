"""M5 智能报告模块 — 阶段1 模拟数据验证

验证模拟数据提供器输出的统一报告输入是否完整覆盖 03 文档的全部边界场景，
并锁定预期结果（人工核对口径）。真实指标计算在阶段2 由计算器实现。
"""
from datetime import datetime

from app.schemas.report import CustomerReportInput
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset


def _newest_time(c: CustomerReportInput) -> datetime | None:
    """客户新增时间 = 首次注册登录 / 首次员工提交 两者更早者。"""
    times = [t for t in (c.first_register_login_at, c.first_employee_submit_at) if t is not None]
    return min(times) if times else None


def _is_in_period(t: datetime | None) -> bool:
    return t is not None and PERIOD_START <= t < PERIOD_END


def _dedup_by_phone(customers: list[CustomerReportInput]) -> list[CustomerReportInput]:
    """按手机号去重，保留最早新增时间的一条（与口径一致）。"""
    best: dict[str, CustomerReportInput] = {}
    for c in customers:
        t = _newest_time(c)
        cur = best.get(c.phone)
        if cur is None or (t is not None and (_newest_time(cur) is None or t < _newest_time(cur))):
            best[c.phone] = c
    return list(best.values())


def test_dataset_builds_and_meta():
    ds = build_mock_dataset()
    assert ds.is_mock is True
    assert ds.period_start == PERIOD_START
    assert ds.period_end == PERIOD_END
    assert ds.data_updated_at <= PERIOD_END


def test_customer_scenarios():
    ds = build_mock_dataset()
    cs = ds.customers

    # 场景：两个渠道相同手机号（去重）—— 14 条记录中仅 13 个唯一手机号
    phones = [c.phone for c in cs]
    assert len(phones) == 14
    assert len(set(phones)) == 13
    assert phones.count("13800000013") == 2  # 去重样本存在

    # 场景：期末六种状态各有样本
    statuses = {c.status_at_period_end for c in cs}
    assert statuses == {"NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST"}

    # 场景：本期新增（新增时间在周期内），按手机号去重后 = 9
    new_this_period = _dedup_by_phone([c for c in cs if _is_in_period(_newest_time(c))])
    assert len(new_this_period) == 9

    # 场景：本期新增去向四项合计 = 新增数（意向/签约/入学/流失）
    intent_statuses = {"NEW", "FOLLOWING", "STRONG"}
    outcomes = {
        "意向": sum(1 for c in new_this_period if c.status_at_period_end in intent_statuses),
        "已签约": sum(1 for c in new_this_period if c.status_at_period_end == "SIGNED"),
        "已入学": sum(1 for c in new_this_period if c.status_at_period_end == "ENROLLED"),
        "已流失": sum(1 for c in new_this_period if c.status_at_period_end == "LOST"),
    }
    assert sum(outcomes.values()) == 9
    assert outcomes == {"意向": 5, "已签约": 1, "已入学": 1, "已流失": 2}

    # 场景：回流客户不计入新增（新增时间在周期外）
    reflowed = [c for c in cs if c.reflowed]
    assert reflowed and all(not _is_in_period(_newest_time(c)) for c in reflowed)

    # 场景：自动流失与人工流失分开
    lost = [c for c in cs if c.status_at_period_end == "LOST"]
    assert {c.status_source for c in lost} == {"auto", "manual"}

    # 场景：无研判结果 -> sg/de 为 None（v6.11.0：无研判不补值、不计入分母）
    assert any(c.sg_conclusion is None and c.de_conclusion is None for c in cs)

    # 场景：画像四分类均有样本（v6.11.0 §2.3）
    for attr in ("sg_conclusion", "de_conclusion"):
        vals = {getattr(c, attr) for c in cs if getattr(c, attr) is not None}
        assert vals == {"符合", "部分符合", "不符合", "信息不足"}


def test_employee_scenarios():
    ds = build_mock_dataset()
    reports = ds.daily_reports
    from datetime import date

    # 场景：周一至周五各有提交；周末也有提交（不计应交/未交）
    weekdays = {date(2026, 10, d) for d in range(12, 17)}
    report_dates = {r.report_date for r in reports}
    assert weekdays.issubset(report_dates)
    assert date(2026, 10, 17) in report_dates  # 周六提交

    # 场景：补交（周二提交、日报日期归周一）
    assert any(r.report_date == date(2026, 10, 12) and r.submitted_at.date() == date(2026, 10, 13) for r in reports)

    # 场景：同一员工同一日报日期重复（e1 周一两条）—— 应被去重计一次
    e1_mon = [r for r in reports if r.employee_id == 1 and r.report_date == date(2026, 10, 12)]
    assert len(e1_mon) == 2  # 样本存在，去重逻辑在阶段2计算器

    # 场景：多部门
    assert {r.department for r in reports} == {"咨询部", "教务部", "市场部"}


def test_psych_scenarios():
    ds = build_mock_dataset()
    ps = ds.psych_records

    # 场景：同一学生多条记录按学生去重 -> 4 个唯一学生
    assert len(ps) == 5
    assert len({p.student_id for p in ps}) == 4

    # 场景：风险等级高/中/低均有样本
    assert {p.risk_level for p in ps} == {"高", "中", "低"}


def test_complaint_scenarios():
    ds = build_mock_dataset()
    ts = ds.complaints

    # 场景：投诉/建议/咨询混合，只有"投诉"计入（v6.11.0 增加 1 条待分析工单 t11）
    complaints = [t for t in ts if t.feedback_type == "投诉"]
    assert len(ts) == 11
    assert len(complaints) == 9
    # 待分析工单用于演示「只计工单总量、不进 AI 指标」
    assert any(t.analysis_status == "pending" for t in ts)
    assert any(t.analysis_status == "analyzed" for t in ts)

    # 场景：已响应 / 未响应均有
    assert any(t.first_response_at is not None for t in complaints)
    assert any(t.first_response_at is None for t in complaints)

    # 场景：已解决 / 未解决均有
    assert any(t.status == "resolved" for t in complaints)
    assert any(t.status == "open" for t in complaints)

    # 场景：恰好 7×24h（10-12 00:00）与超过 7×24h（10-11 23:59）边界
    deadline = PERIOD_END
    unresolved_over7 = [t for t in complaints if t.status == "open"
                        and (deadline - t.submitted_at).total_seconds() > 7 * 24 * 3600]
    assert len(unresolved_over7) == 2  # t3(10-06) 与 t8(10-11 23:59)
    # 恰好 7×24h 不算长期未解决（10-12 00:00 提交）
    assert any(t.ticket_id == 4 and t.status == "open" for t in complaints)

    # 场景：满意度 满意/不满意/未评价 均有
    assert {t.satisfaction for t in complaints} == {"满意", "不满意", "未评价"}

    # 场景：v6.11.0 一期 AI 判定（无人工复核）→ 高风险即特别案例，且带 AI 归纳理由
    high_risk = [t for t in complaints if t.ai_high_risk and t.analysis_status == "analyzed"]
    assert len(high_risk) >= 2
    assert all(t.ai_summary for t in high_risk)
