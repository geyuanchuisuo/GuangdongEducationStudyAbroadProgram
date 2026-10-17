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

from app.models.crm import CustomerAssessment
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport
from app.models.student import StudentPsychAlert, StudentPsychProfile
from app.models.user import User
from app.schemas.report import (
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


# 画像 4→3 映射（M5-03.4，保守默认，正式映射待业务拍板——见 docs/M5_字段映射表.md 待确认列）
_PROFILE_4_TO_3 = {
    "matched": "符合",
    "not_matched": "不符合",
    # partial / pending / 未知值一律归"信息不足"并标注，不擅自给业务结论
    "partial": "信息不足",
    "pending": "信息不足",
}


def _map_profile(conclusion: str | None) -> str | None:
    if conclusion is None:
        return None
    return _PROFILE_4_TO_3.get(conclusion, "信息不足")


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
    """客户经营输入：customer 主表 + 最新有效研判（两表分别查询，内存拼接，不 JOIN）。

    逐行容错（M5-10.7）：单行状态值/字段异常只跳过该行并计入口径说明，
    不允许一行脏数据把 5 类报告全部打成 500。
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
        latest_assess.setdefault(a.customer_id, a)

    inputs: list[CustomerReportInput] = []
    skipped: list[str] = []
    for c in custs:
        a = latest_assess.get(c.id)
        status_code = normalize_customer_status(c.status)
        if status_code is None:
            skipped.append(f"id={c.id} status={c.status!r}")
            continue
        try:
            inputs.append(CustomerReportInput(
                customer_id=c.id,
                phone=c.phone,
                name=c.name or "",
                source_channel=c.source_channel or "",
                first_register_login_at=c.first_register_at,
                first_employee_submit_at=c.first_submit_at,
                status_at_period_end=status_code,
                status_source=_status_source(c, status_code),
                reflowed=c.reflowed_at is not None,
                latest_assessment_at=a.created_at if a else None,
                sg_conclusion=_map_profile(a.sg_conclusion) if a else None,
                de_conclusion=_map_profile(a.de_conclusion) if a else None,
                owner_employee_id=c.owner_employee_id,
                follow_up_summary=None,  # 跟进摘要未纳入（见字段映射表：待确认是否需要）
            ))
        except Exception as exc:  # noqa: BLE001 — 单行不合规不阻断整份报告
            skipped.append(f"id={c.id} {type(exc).__name__}")
            logger.warning("M5 客户行跳过: customer_id=%s error=%s", c.id, exc)
    status = "ok" if inputs else "empty"
    note = f"客户域：读取 {len(inputs)} 条有效客户（手机号非空）；最新有效研判 {len(latest_assess)} 条"
    if skipped:
        note += (f"；跳过 {len(skipped)} 行状态/字段不合规"
                 f"（示例：{', '.join(skipped[:3])}）")
    return DomainResult(status=status, note=note, inputs=inputs)


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

    inputs: list[PsychReportInput] = []
    for sid, d in agg.items():
        alert, profile = d["alert"], d["profile"]
        inputs.append(PsychReportInput(
            student_id=sid,
            record_at=max(t for t in d["times"] if t is not None),
            emotion_tag=profile.latest_emotion_tag if profile else None,
            risk_level=(alert.risk_level if alert and alert.risk_level in ("高", "中", "低") else None),
            feedback_summary=None,  # 预警原文不进报告（脱敏）
            responsible_employee_id=alert.teacher_id if alert else None,
        ))
    status = "ok" if inputs else "empty"
    note = (f"心理域：周期内预警 {len(alert_rows)} 条 + 画像交互 {len(profile_rows)} 条，"
            f"按学生聚合 {len(inputs)} 人；负责员工仅预警记录有（teacher_id），画像记录缺该字段")
    return DomainResult(status=status, note=note, inputs=inputs)


async def fetch_complaints(db: AsyncSession, start: datetime, end: datetime) -> DomainResult:
    """投诉域：M5-03.1 阻塞项——工单表缺 9 个报告字段，明确不可得，不伪造。"""
    return DomainResult(
        status="data_unavailable",
        note="投诉域：数据不可得——student_feedback_ticket 缺 9 个报告字段"
             "（feedback_type/first_response_at/resolved_at/满意度/review_status/"
             "ai_high_risk/ai_low_score/owner_id/progress），需 M4 落库后开放（见字段映射表）",
        inputs=[],
    )
