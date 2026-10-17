"""M5 智能报告模块 — 下钻数据（阶段 4）

下钻只返回脱敏 / 最小必要字段；心理个案按角色过滤；投诉特别案例只返回已复核。
纯函数，接受统一报告输入（MockReportDataset），后续真实数据适配器复用。
"""
from app.core.exceptions import ForbiddenError
from app.models.user import User
from app.schemas.report import MockReportDataset
from app.services.report_calculator import dedup_customers_by_phone


def mask_phone(phone: str) -> str:
    """手机号脱敏：保留前 3 后 4，中间打码。"""
    if len(phone) >= 7:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone


def customer_drilldown(ds: MockReportDataset) -> list[dict]:
    """客户下钻：全部有效客户（去重），仅最小必要字段、手机号脱敏。"""
    return [
        {
            "customer_id": c.customer_id,
            "name": c.name,
            "phone": mask_phone(c.phone),
            "status": c.status_at_period_end,
            "source_channel": c.source_channel,
            "owner_employee_id": c.owner_employee_id,
            "sg_conclusion": c.sg_conclusion,
            "de_conclusion": c.de_conclusion,
            "follow_up_summary": c.follow_up_summary,
        }
        for c in dedup_customers_by_phone(ds.customers)
    ]


def _latest_psych_cases(ds: MockReportDataset, start, end) -> list[dict]:
    records = [r for r in ds.psych_records if start <= r.record_at < end]
    latest: dict[int, object] = {}
    for r in records:
        cur = latest.get(r.student_id)
        if cur is None or r.record_at >= cur.record_at:
            latest[r.student_id] = r
    return [
        {
            "student_id": c.student_id,
            "emotion_tag": c.emotion_tag,
            "risk_level": c.risk_level,
            "feedback_summary": c.feedback_summary,
            "responsible_employee_id": c.responsible_employee_id,
        }
        for c in latest.values()
    ]


def psych_cases_for_user(ds: MockReportDataset, start, end, user: User) -> list[dict]:
    """心理个案：MANAGER/ADMIN 看全部，EMPLOYEE 只看自己负责，其余角色拒绝。"""
    if user.user_type not in ("ADMIN", "MANAGER", "EMPLOYEE"):
        raise ForbiddenError(message="无权限查看心理个案")
    cases = _latest_psych_cases(ds, start, end)
    if user.user_type == "EMPLOYEE":
        cases = [c for c in cases if c["responsible_employee_id"] == user.id]
    return cases


def special_cases_drilldown(ds: MockReportDataset) -> list[dict]:
    """投诉特别案例：仅已复核通过，只返回案例编号 / 负责人 / 处理进度。"""
    complaints = [t for t in ds.complaints if t.feedback_type == "投诉"]
    return [
        {"ticket_id": t.ticket_id, "owner_id": t.owner_id, "progress": t.progress}
        for t in complaints if t.ai_high_risk and t.review_status == "approved"
    ]
