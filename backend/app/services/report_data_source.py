"""M5 智能报告模块 — 真实数据适配器（M5-02.1，批次 C 骨架）。

把 M1/M3/M4 真实业务查询规范化为统一报告输入（app/schemas/report.py）。
硬约束（AGENTS.md + 改码提示词）：
- 只读 SELECT，逐表独立查询后内存拼接，不跨模块 JOIN 别人的表
- 不修改其他模块模型；缺失字段不伪造，显式标记（投诉 9 字段未落库 → data_unavailable）
- 读取失败向上抛 DomainReadError，由编排层标记 read_failed，禁止回落 mock（M5-02.4）

每个数据域返回 DomainResult：inputs + status + note。
status 三态口径（M5-02.5）：ok（读到数据）/ empty（读取成功但周期内无记录）/
read_failed（读取失败）/ data_unavailable（所需字段未落库）。
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import CustomerAssessment, TicketAIAnalysis
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport
from app.models.student import StudentFeedbackTicket, StudentPsychAlert, StudentPsychProfile
from app.models.user import User
from app.schemas.report import (
    ComplaintReportInput,
    CustomerReportInput,
    EmployeeDailyReportInput,
    EmployeeInput,
    PsychReportInput,
)
# 客户 6 态词表以 M1 为单一来源（中文值由 M1/M3 写入，M5 只做归一）
from app.services.customer_service import CUSTOMER_STATUSES, STATUS_CN_TO_EN

logger = logging.getLogger(__name__)


class DomainReadError(RuntimeError):
    """某数据域读取失败（M5-02.4：生产模式必须显式标记，不允许静默回落）。"""


@dataclass
class DomainResult:
    status: str                      # ok / empty / read_failed / data_unavailable
    note: str = ""
    inputs: list = field(default_factory=list)
    # v6.11.0：本域中「取不到、已标不可得」的字段名，写进报告 data_quality_detail
    unavailable_fields: list[str] = field(default_factory=list)


# 画像四类映射（v6.11.0 需求确认 §2.3：四类独立）
_PROFILE_MAP = {
    "matched": "符合",
    "partial": "部分符合",
    "not_matched": "不符合",
    "pending": "信息不足",
}


def _map_profile(conclusion: str | None) -> str | None:
    if conclusion is None:
        return None
    return _PROFILE_MAP.get(conclusion, "信息不足")


def _status_source(c: Customer, status_code: str | None) -> str | None:
    """流失来源（仅 LOST 有意义）：系统自动流失标记=auto，否则人工=manual。"""
    if status_code != "LOST":
        return None
    return "auto" if c.auto_churned else "manual"


def normalize_customer_status(raw: str | None) -> str | None:
    """客户 6 态归一为英文编码（M5-10.7）。

    M1 契约 `CustomerStatusChange` 明确允许「英文或中文 6 态」，M3 也会写入中文值，
    因此 M5 取数时必须先归一，否则 Literal 校验会直接抛错把整份报告打断。
    词表复用 M1 的 `STATUS_CN_TO_EN`（单一来源，避免两套词表漂移）；
    未识别的值返回 None，由调用方按行跳过并计入口径说明。
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value in CUSTOMER_STATUSES:
        return value
    upper = value.upper()
    if upper in CUSTOMER_STATUSES:
        return upper
    return STATUS_CN_TO_EN.get(value)


async def fetch_customers(db: AsyncSession, start: datetime, end: datetime) -> DomainResult:
    """客户经营输入：customer 主表 + 周期末前最新有效研判（两表分别查询，内存拼接，不 JOIN）。

    v6.11.0 口径（需求确认 §2.3/§六）：
    - **期末状态不可得**：M1 尚无历史时点状态能力，禁止用当前值冒充周期末值 →
      `status_at_period_end` 置 None，由计算器把依赖状态的指标标「数据不可得」；
    - **研判按时点过滤**：只用 `created_at < 周期末` 的研判（周期后产生的研判不用于该周期）；
    - 逐行容错：单行字段异常只跳过该行并计入口径说明，不允许拖垮整份报告。

    注：本期仍直读 M1 表（规范要求走模块接口，受上游接口阻塞，见 docs/M5_上游接口契约.md）。
    """
    try:
        custs = (await db.execute(select(Customer).where(Customer.phone.isnot(None)))).scalars().all()
        assess_rows = (
            await db.execute(
                select(CustomerAssessment)
                .where(CustomerAssessment.status == "valid", CustomerAssessment.customer_id.isnot(None))
                .order_by(CustomerAssessment.id.desc())
            )
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("M5 客户域读取失败: %s", exc)
        raise DomainReadError(f"客户数据读取失败: {exc}") from exc

    latest_assess: dict[int, CustomerAssessment] = {}
    for a in assess_rows:  # id 倒序 → 首见即最新
        if a.created_at is not None and a.created_at >= end:
            continue  # 周期后产生的研判不用于该周期
        latest_assess.setdefault(a.customer_id, a)

    inputs: list[CustomerReportInput] = []
    skipped: list[str] = []
    for c in custs:
        a = latest_assess.get(c.id)
        try:
            inputs.append(CustomerReportInput(
                customer_id=c.id,
                phone=c.phone,
                name=c.name or "",
                source_channel=c.source_channel or "",
                first_register_login_at=c.first_register_at,
                first_employee_submit_at=c.first_submit_at,
                # 不可得：不用当前值冒充周期末状态
                status_at_period_end=None,
                status_source=None,
                reflowed=c.reflowed_at is not None,
                latest_assessment_at=a.created_at if a else None,
                sg_conclusion=_map_profile(a.sg_conclusion) if a else None,
                de_conclusion=_map_profile(a.de_conclusion) if a else None,
                owner_employee_id=c.owner_employee_id,
                follow_up_summary=None,  # 跟进摘要一期不取（见字段映射表）
            ))
        except Exception as exc:  # noqa: BLE001 — 单行不合规不阻断整份报告
            skipped.append(f"id={c.id} {type(exc).__name__}")
            logger.warning("M5 客户行跳过: customer_id=%s error=%s", c.id, exc)

    status = "ok" if inputs else "empty"
    note = (f"客户域：读取 {len(inputs)} 条有效客户（手机号非空）；"
            f"周期末前有效研判 {len(latest_assess)} 条")
    note += ("；期末状态：不可得（M1 无历史时点能力，不用当前值冒充周期末值，"
             "依赖状态的指标标「数据不可得」）")
    if skipped:
        note += (f"；跳过 {len(skipped)} 行字段不合规"
                 f"（示例：{', '.join(skipped[:3])}）")
    return DomainResult(
        status=status,
        note=note,
        inputs=inputs,
        unavailable_fields=["status_at_period_end"],
    )


async def fetch_employees_and_daily_reports(
    db: AsyncSession, start: datetime, end: datetime
) -> tuple[DomainResult, DomainResult]:
    """员工花名册 + 日报输入（M3 域）。有效提交=status=submitted（draft/late_pending 不计）。"""
    try:
        users = (
            await db.execute(
                select(User).where(User.user_type == "EMPLOYEE", User.status == "正常")
            )
        ).scalars().all()
        report_rows = (
            await db.execute(
                select(EmployeeDailyReport)
                .where(
                    EmployeeDailyReport.report_date >= start.date(),
                    EmployeeDailyReport.report_date < end.date(),
                    EmployeeDailyReport.status == "submitted",
                )
            )
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("M5 员工域读取失败: %s", exc)
        raise DomainReadError(f"员工/日报数据读取失败: {exc}") from exc

    dept_map = {u.id: (u.department or "未分配") for u in users}
    emp_inputs = [
        EmployeeInput(employee_id=u.id, department=dept_map[u.id], employment_status="active")
        for u in users
    ]
    report_inputs = [
        EmployeeDailyReportInput(
            employee_id=r.employee_id,
            department=dept_map.get(r.employee_id, "未分配"),
            report_date=r.report_date,
            submitted_at=r.create_time or datetime.combine(r.report_date, datetime.min.time()),
            content=r.content,
            is_valid=True,  # 查询已过滤 status=submitted
        )
        for r in report_rows
    ]
    emp_res = DomainResult(
        status="ok" if emp_inputs else "empty",
        note=f"员工域：在职员工 {len(emp_inputs)} 人（user_type=EMPLOYEE 且状态正常）",
        inputs=emp_inputs,
    )
    rep_res = DomainResult(
        status="ok" if report_inputs else "empty",
        note=f"日报域：有效提交 {len(report_inputs)} 条（status=submitted；draft/late_pending 不计；"
             f"is_late 迟报口径未入报告，见字段映射表）",
        inputs=report_inputs,
    )
    return emp_res, rep_res


async def fetch_psych(db: AsyncSession, start: datetime, end: datetime) -> DomainResult:
    """心理输入（M4 域）：按学生聚合——风险取周期内最新预警、情绪取最新画像交互、
    record_at 取该学生最晚记录时间；反馈原文不取（PDF 脱敏口径）。"""
    try:
        alert_rows = (
            await db.execute(
                select(StudentPsychAlert).where(
                    StudentPsychAlert.create_time >= start,
                    StudentPsychAlert.create_time < end,
                ).order_by(StudentPsychAlert.id.asc())
            )
        ).scalars().all()
        profile_rows = (
            await db.execute(
                select(StudentPsychProfile).where(
                    StudentPsychProfile.last_interaction_time >= start,
                    StudentPsychProfile.last_interaction_time < end,
                )
            )
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("M5 心理域读取失败: %s", exc)
        raise DomainReadError(f"心理数据读取失败: {exc}") from exc

    agg: dict[int, dict] = {}
    for a in alert_rows:  # id 升序遍历 → 后见覆盖 = 最新预警
        d = agg.setdefault(a.student_id, {"alert": None, "profile": None, "times": []})
        d["alert"] = a
        d["times"].append(a.create_time)
    for p in profile_rows:
        d = agg.setdefault(p.student_id, {"alert": None, "profile": None, "times": []})
        if d["profile"] is None or (p.last_interaction_time or datetime.min) >= (
            d["profile"].last_interaction_time or datetime.min
        ):
            d["profile"] = p
        d["times"].append(p.last_interaction_time)

    # v6.11.0 §2.5：心理个案授权后可见身份/联系方式 → 只读 sys_user 最小字段
    user_map: dict[int, tuple[str | None, str | None]] = {}
    try:
        ids = list(agg.keys())
        if ids:
            rows = (await db.execute(
                select(User.id, User.real_name, User.phone).where(User.id.in_(ids))
            )).all()
            user_map = {r[0]: (r[1], r[2]) for r in rows}
    except Exception as exc:  # noqa: BLE001 — 身份字段失败不影响统计
        logger.warning("M5 心理域身份字段读取失败: %s", exc)

    inputs: list[PsychReportInput] = []
    for sid, d in agg.items():
        alert, profile = d["alert"], d["profile"]
        name, phone = user_map.get(sid, (None, None))
        inputs.append(PsychReportInput(
            student_id=sid,
            record_at=max(t for t in d["times"] if t is not None),
            emotion_tag=profile.latest_emotion_tag if profile else None,
            risk_level=(alert.risk_level if alert and alert.risk_level in ("高", "中", "低") else None),
            feedback_summary=(alert.trigger_reason if alert and alert.trigger_reason else None),
            feedback_raw=(alert.trigger_reason if alert and alert.trigger_reason else None),
            responsible_employee_id=alert.teacher_id if alert else None,
            student_name=name,
            student_contact=phone,
        ))
    status = "ok" if inputs else "empty"
    note = (f"心理域：周期内预警 {len(alert_rows)} 条 + 画像交互 {len(profile_rows)} 条，"
            f"按学生聚合 {len(inputs)} 人；负责员工仅预警记录有（teacher_id），"
            f"身份/联系方式来自 sys_user（{len(user_map)} 人可解析）")
    unavailable = []
    if not any(i.responsible_employee_id for i in inputs):
        unavailable.append("responsible_employee_id")
    return DomainResult(status=status, note=note, inputs=inputs, unavailable_fields=unavailable)


_TICKET_STATUS_RESOLVED = {"已解决", "已关闭", "resolved", "closed"}


async def fetch_complaints(db: AsyncSession, start: datetime, end: datetime) -> DomainResult:
    """投诉域（v6.11.0 §2.6 部分可用口径）。

    M4 工单表目前只有 content/detail/status/时间，缺「学生所选类型、首次响应时间、
    解决时间、满意度、负责人、处理过程、AI 字段」。按「部分生成 + 标不可得」原则：
    - 可读字段照常读（原文、提交时间、状态、解决时间）；
    - 缺的字段标不可得，不填零、不推测；
    - AI 分析来自 M5 自建的 ticket_ai_analysis（不改 M4 表），无成功记录即「待分析」。
    """
    try:
        tickets = (await db.execute(select(StudentFeedbackTicket))).scalars().all()
        analyses = (
            await db.execute(select(TicketAIAnalysis).order_by(TicketAIAnalysis.id.desc()))
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("M5 投诉域读取失败: %s", exc)
        raise DomainReadError(f"投诉数据读取失败: {exc}") from exc

    latest_analysis: dict[int, TicketAIAnalysis] = {}
    for a in analyses:  # id 倒序 → 首见即最近一次
        latest_analysis.setdefault(a.ticket_id, a)

    # v6.11.0 §2.6：特别案例允许完整详情 → 需要学生身份/联系方式（只读 sys_user 最小字段）
    user_map: dict[int, tuple[str | None, str | None]] = {}
    try:
        sids = list({t.student_id for t in tickets})
        if sids:
            rows = (await db.execute(
                select(User.id, User.real_name, User.phone).where(User.id.in_(sids))
            )).all()
            user_map = {r[0]: (r[1], r[2]) for r in rows}
    except Exception as exc:  # noqa: BLE001
        logger.warning("M5 投诉域身份字段读取失败: %s", exc)

    inputs: list[ComplaintReportInput] = []
    skipped: list[str] = []
    for t in tickets:
        created = t.create_time
        if created is None:
            skipped.append(f"id={t.id} 无创建时间")
            continue
        a = latest_analysis.get(t.id)
        succeeded = a is not None and a.status == "succeeded"
        category = a.category if succeeded and a.category in ("投诉", "建议", "咨询") else None
        resolved = (t.status or "") in _TICKET_STATUS_RESOLVED
        sname, sphone = user_map.get(t.student_id, (None, None))
        try:
            inputs.append(ComplaintReportInput(
                ticket_id=t.id,
                student_id=t.student_id,
                # 类型来源：有 AI 分类则标 ai，否则 unknown（学生所选类型字段 M4 未落库）
                feedback_type=category or "投诉",
                category_source="ai" if category else "unknown",
                submitted_at=created,
                # M4 未记录首次响应时间 → 不可得
                first_response_at=None,
                resolved_at=t.update_time if resolved else None,
                status="resolved" if resolved else "open",
                # 满意度只取学生明确评价；M4 未落库 → 一律「未评价」，不推测
                satisfaction="未评价",
                ai_low_score=bool(a.low_satisfaction_candidate) if succeeded else False,
                ai_high_risk=bool(a.high_risk) if succeeded else False,
                review_status="pending",
                owner_id=None,
                progress=None,
                analysis_status=(
                    "analyzed" if succeeded else ("failed" if a is not None and a.status == "failed" else "pending")
                ),
                analysis_record_id=a.id if a else None,
                ai_summary=a.summary if succeeded else None,
                content=t.content,
                detail=t.detail,
                student_name=sname,
                student_contact=sphone,
            ))
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"id={t.id} {type(exc).__name__}")
            logger.warning("M5 投诉行跳过: ticket_id=%s error=%s", t.id, exc)

    unavailable = [
        "feedback_type(学生所选)",
        "first_response_at",
        "satisfaction",
        "owner_id",
        "progress",
    ]
    note = (
        f"投诉域：读取工单 {len(inputs)} 条；其中已 AI 分析 "
        f"{sum(1 for x in inputs if x.analysis_status == 'analyzed')} 条、"
        f"待分析 {sum(1 for x in inputs if x.analysis_status != 'analyzed')} 条；"
        f"不可得字段：{('、'.join(unavailable))}（M4 未落库，等对应负责人）"
    )
    if skipped:
        note += f"；跳过 {len(skipped)} 行（示例：{', '.join(skipped[:3])}）"
    return DomainResult(
        status="ok" if inputs else "empty",
        note=note,
        inputs=inputs,
        unavailable_fields=unavailable,
    )
