"""M5 智能报告模块 — 下钻数据（v6.11.0 快照口径）

口径变更（需求确认 2026-10-18）：
- 下钻数据在**生成报告时固化进快照**，读取旧报告不再查实时业务数据（§2.2/§五）；
- 心理个案：授权角色可看**完整个案**（身份、联系方式、反馈原文、历史记录），
  权限=MANAGER/ADMIN 全部、EMPLOYEE 仅自己负责、其余拒绝（§2.5/§2.9）；
- 投诉特别案例：AI 判定（一期无人工复核），网页与 PDF 均允许完整详情，仅 MANAGER/ADMIN（§2.6）；
- 客户下钻：最小必要字段 + 手机号脱敏（§2.3）。

本模块只做数据整形，不做权限判断以外的 IO。
"""
from app.core.exceptions import ForbiddenError
from app.models.user import User
from app.schemas.report import MockReportDataset
from app.services.report_calculator import dedup_customers_by_phone, is_special_case


def mask_phone(phone: str | None) -> str | None:
    """手机号脱敏：保留前 3 后 4，中间打码。"""
    if not phone:
        return None
    if len(phone) >= 7:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone


# ── 客户（§2.3：最小必要字段 + 脱敏） ─────────────────────

def customer_drilldown(ds: MockReportDataset) -> list[dict]:
    """客户下钻快照：全部有效客户（按手机号去重），含负责人与最新研判，不含画像依据。"""
    return [
        {
            "customer_id": c.customer_id,
            "name": c.name,
            "phone": mask_phone(c.phone),
            "status": c.status_at_period_end,          # None = 期末状态不可得
            "source_channel": c.source_channel,
            "owner_employee_id": c.owner_employee_id,
            "latest_assessment_at": (
                c.latest_assessment_at.isoformat() if c.latest_assessment_at else None
            ),
            "sg_conclusion": c.sg_conclusion,
            "de_conclusion": c.de_conclusion,
            "follow_up_summary": c.follow_up_summary,
        }
        for c in dedup_customers_by_phone(ds.customers)
    ]


# ── 心理个案（§2.5：完整个案，按角色过滤） ────────────────

def psych_cases_snapshot(ds: MockReportDataset, start, end) -> list[dict]:
    """心理个案快照（未过滤角色，读取时按 responsible_employee_id 过滤）。

    含身份、联系方式、反馈原文与周期内历史记录——这些字段依赖 M4 提供，
    缺失时为 None（不伪造）。快照一旦生成即固化，后续补录不会改变旧报告。
    """
    in_period = [r for r in ds.psych_records if start <= r.record_at < end]
    latest: dict[int, object] = {}
    history: dict[int, list[dict]] = {}
    for r in in_period:
        history.setdefault(r.student_id, []).append({
            "record_at": r.record_at.isoformat(),
            "emotion_tag": r.emotion_tag,
            "risk_level": r.risk_level,
            "feedback_summary": r.feedback_summary,
        })
        cur = latest.get(r.student_id)
        if cur is None or r.record_at >= cur.record_at:
            latest[r.student_id] = r
    cases = []
    for student_id, c in latest.items():
        cases.append({
            "student_id": student_id,
            "student_name": c.student_name,
            "student_contact": mask_phone(c.student_contact),
            "emotion_tag": c.emotion_tag,
            "risk_level": c.risk_level,
            "feedback_summary": c.feedback_summary,
            "feedback_raw": c.feedback_raw,
            "responsible_employee_id": c.responsible_employee_id,
            "history": sorted(history.get(student_id, []), key=lambda x: x["record_at"]),
        })
    return cases


def filter_psych_cases(cases: list[dict], user: User) -> list[dict]:
    """心理个案角色过滤：MANAGER/ADMIN 全部、EMPLOYEE 仅自己负责、其余拒绝。"""
    if user.user_type not in ("ADMIN", "MANAGER", "EMPLOYEE"):
        raise ForbiddenError(message="无权限查看心理个案")
    if user.user_type == "EMPLOYEE":
        return [c for c in cases if c.get("responsible_employee_id") == user.id]
    return cases


# ── 投诉特别案例（§2.6：AI 判定，仅 MANAGER/ADMIN 可见完整详情） ──

def special_cases_snapshot(ds: MockReportDataset) -> list[dict]:
    """投诉特别案例快照：AI 判定的高风险案例，含身份、工单原文与处理过程。"""
    rows = []
    for t in ds.complaints:
        if not is_special_case(t):
            continue
        rows.append({
            "ticket_id": t.ticket_id,
            "student_id": t.student_id,
            "student_name": t.student_name,
            "student_contact": mask_phone(t.student_contact),
            "feedback_type": t.feedback_type,
            "category_source": t.category_source,
            "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            "status": t.status,
            "satisfaction": t.satisfaction,
            "content": t.content,
            "detail": t.detail,
            "ai_summary": t.ai_summary,
            "special_reason": t.ai_summary,
            "owner_id": t.owner_id,
            "progress": t.progress,
        })
    return rows
