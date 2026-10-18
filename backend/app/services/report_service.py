"""M5 智能报告模块 — 报告生成编排服务（阶段 3 + 批次 C 生产取数 + v6.11.0 口径）

数据来源由 settings.REPORT_DATA_SOURCE 开关选择（M5-02.3）：
- mock（默认）：模拟数据提供器，参考周期为固定演示周期；
- production：真实业务适配器，**部分可用也生成**，不可得域标「数据不可得」，
  禁止静默回退 mock（v6.11.0 §2.8）。
指标计算、内容结构、版本、接口均不随 provider 变化。

v6.11.0 关键行为：
- 下钻在生成时固化快照（§2.2），旧报告的详情/下钻/PDF 不再查实时库；
- AI 优先走报告专用 Agent（经公共网关）；当前 M0 未登记 REPORT，按 v6.11.10 决策走已有降级路径。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.core.exceptions import BusinessError, NotFoundError, ValidationError
from app.models.crm import AiReport, AiReportDrill
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.schemas.report import MockReportDataset
from app.services.report_ai_service import ReportAIService
from app.services.report_calculator import calculate_customer_stats
from app.services.report_content import REPORT_TYPE_NAMES, build_report_content
from app.services.report_data_source import (
    DomainReadError,
    fetch_complaints,
    fetch_customers,
    fetch_employees_and_daily_reports,
    fetch_psych,
)
from app.services.report_drilldown import (
    customer_drilldown,
    filter_psych_cases,
    psych_cases_snapshot,
    special_cases_snapshot,
)
from app.services.report_mock_data import build_mock_dataset
from app.services.report_pdf import generate_report_pdf
from app.utils.report_period import (
    PeriodValidationError,
    default_completed_week,
    validate_period,
    week_range,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2  # M5-12.2：生成失败自动重试一次，仍失败落 failed 记录


class ReportService:
    def __init__(self, repo: ReportRepository, ai: ReportAIService | None = None):
        self.repo = repo
        self.ai = ai or ReportAIService()

    async def generate(
        self,
        report_type: str,
        period_start: datetime | None,
        period_end: datetime | None,
        user_id: int,
    ) -> AiReport:
        if report_type not in REPORT_TYPE_NAMES:
            raise ValidationError(message=f"不支持的报告类型: {report_type}")

        # v6.11.0：production 部分生成——某域失败只标「数据不可得」，不整体拒绝
        if settings.REPORT_DATA_SOURCE == "production":
            ds, data_quality, extra_notes, unavailable = await self._build_production_dataset(
                report_type, period_start, period_end
            )
        else:
            ds = build_mock_dataset(period_start, period_end)
            data_quality, extra_notes, unavailable = None, None, None
        start = ds.period_start
        end = ds.period_end
        # M5-04.2 周期合法性：对齐自然周/月边界、跨度、顺序；未来周期校验仅对
        # 非模拟数据生效（mock 参考周期是演示用的固定周期，不受真实时钟约束）
        try:
            validate_period(start, end, check_future=not ds.is_mock)
        except PeriodValidationError as exc:
            raise ValidationError(message=str(exc))

        # M5-12.2：生成失败重试一次；仍失败落 status=failed + error_message 后抛错
        version = await self.repo.next_version(report_type, start, end)
        last_exc: Exception | None = None
        for _ in range(_MAX_ATTEMPTS):
            try:
                content = build_report_content(
                    report_type, ds, start, end, version, datetime.now(),
                    data_quality=data_quality, extra_notes=extra_notes,
                    unavailable=unavailable,
                    comparison=await self._build_comparison(report_type, ds, start, end),
                    sections=(
                        {"special_cases": special_cases_snapshot(ds)}
                        if report_type == "complaint_weekly" else None
                    ),
                )
                # 阶段 5：AI 只写文字，失败不阻断确定性统计
                analysis = await self.ai.analyze(
                    report_type, content["metrics"],
                    context=self._ai_context(report_type, ds, start, end),
                )
                if analysis:
                    content.update(analysis)
                    content["ai_status"] = "available"
                else:
                    content["ai_status"] = "unavailable"
                # 差异字段（M5-10.6 / v6.11.0）：dify=报告专用 Agent / mock=演示模拟 / unavailable
                content["ai_source"] = getattr(self.ai, "source", "unavailable")

                report = AiReport(
                    report_type=report_type,
                    report_title=REPORT_TYPE_NAMES[report_type],
                    report_content=content,
                    time_range_start=start,
                    time_range_end=end,
                    generated_by=user_id,
                    status="completed",
                    version=version,
                    data_source_status="production" if not ds.is_mock else "mock",
                )
                # 仓储层在版本号撞唯一约束时自旋重取（M5-06.4）
                created = await self.repo.create(report)
                # v6.11.0 §2.2：下钻快照随报告一起固化，此后旧报告不再查实时库
                await self._save_drill_snapshot(created, ds, start, end)
                return created
            except Exception as exc:  # noqa: BLE001 — 失败要落 failed 记录，不能直接冒泡
                last_exc = exc

        failed = AiReport(
            report_type=report_type,
            report_title=REPORT_TYPE_NAMES[report_type],
            report_content=None,
            time_range_start=start,
            time_range_end=end,
            generated_by=user_id,
            status="failed",
            version=version,
            data_source_status="production" if not ds.is_mock else "mock",
            error_message=str(last_exc)[:2000] if last_exc else "unknown",
        )
        try:
            await self.repo.create(failed)
        except Exception:  # noqa: BLE001 — 连 failed 记录都落不了库时只抛原始错误
            pass
        raise BusinessError(code=50001, message=f"报告生成失败：{last_exc}")

    async def _build_production_dataset(
        self, report_type: str, period_start: datetime | None, period_end: datetime | None
    ) -> tuple[MockReportDataset, dict, list[str], dict]:
        """生产取数（v6.11.0：部分生成 + 标不可得）。

        与旧版差异：**不再因某域失败整体拒绝**——失败的域标 `read_failed`、
        该域输入为空，其余域照常生成；不可得字段进 `unavailable` 写进报告，
        仍然禁止静默回退 mock（§2.8）。

        周期缺省 = **上一完整自然周**（`week_range` 左闭右开、终点恒在未来，
        直接用会被未来校验拒成 40002）。
        """
        db = self.repo.db
        if period_start is None or period_end is None:
            default_start, default_end = default_completed_week(datetime.now())
            start = period_start or default_start
            end = period_end or default_end
        else:
            start, end = period_start, period_end
        data_quality: dict[str, str] = {}
        unavailable: dict[str, list[str]] = {}
        notes: list[str] = []

        customers_res = psych_res = None
        emp_res = rep_res = complaints_res = None
        try:
            customers_res = await fetch_customers(db, start, end)
        except DomainReadError as exc:
            data_quality["customers"] = "read_failed"
            notes.append(f"【客户域读取失败】{exc}")
        try:
            emp_res, rep_res = await fetch_employees_and_daily_reports(db, start, end)
        except DomainReadError as exc:
            data_quality["employees"] = data_quality["daily_reports"] = "read_failed"
            notes.append(f"【员工/日报域读取失败】{exc}")
        try:
            psych_res = await fetch_psych(db, start, end)
        except DomainReadError as exc:
            data_quality["psych"] = "read_failed"
            notes.append(f"【心理域读取失败】{exc}")
        try:
            complaints_res = await fetch_complaints(db, start, end)
        except DomainReadError as exc:
            data_quality["complaints"] = "read_failed"
            notes.append(f"【投诉域读取失败】{exc}")

        for name, res in (("customers", customers_res), ("employees", emp_res),
                          ("daily_reports", rep_res), ("psych", psych_res),
                          ("complaints", complaints_res)):
            if res is None:
                continue
            data_quality[name] = res.status
            if res.note:
                notes.append(res.note)
            if getattr(res, "unavailable_fields", None):
                unavailable[name] = list(res.unavailable_fields)

        ds = MockReportDataset(
            is_mock=False,
            data_updated_at=datetime.now(),
            period_start=start,
            period_end=end,
            customers=customers_res.inputs if customers_res else [],
            employees=emp_res.inputs if emp_res else [],
            daily_reports=rep_res.inputs if rep_res else [],
            psych_records=psych_res.inputs if psych_res else [],
            complaints=list(complaints_res.inputs) if complaints_res else [],
        )
        return ds, data_quality, notes, unavailable

    # ── AI 上下文（v6.11.0 §2.4：日报/周报只做整体或部门层归纳） ──

    def _ai_context(
        self, report_type: str, ds: MockReportDataset, start: datetime, end: datetime
    ) -> dict | None:
        """给 AI 的补充上下文：只放**部门层聚合文本**，不放个人原文与个人绩效线索。"""
        if report_type not in ("daily_report_summary", "weekly_report_summary"):
            return None
        by_dept: dict[str, list[str]] = {}
        for r in ds.daily_reports:
            if not r.is_valid or not (start <= datetime.combine(r.report_date, datetime.min.time()) < end):
                continue
            text = (r.content or "").strip()
            if text:
                by_dept.setdefault(r.department or "未分组", []).append(text[:200])
        if not by_dept:
            return None
        # 每部门最多 20 条、单条 200 字，且不携带员工标识（匿名聚合）
        digest = {
            dept: texts[:20] for dept, texts in by_dept.items()
        }
        return {
            "note": "以下为部门层日报正文摘录（已匿名，无员工标识）；只能做整体/部门级工作进展、产出、风险归纳，"
                    "禁止评价个人绩效、禁止编造数字与事实。",
            "department_reports": digest,
        }

    # ── 对比口径（v6.11.0 §2.3：客户月报默认与上一个自然月比较） ──

    async def _build_comparison(
        self, report_type: str, ds: MockReportDataset, start: datetime, end: datetime
    ) -> dict | None:
        if report_type != "customer_analysis":
            return None
        # 只有自然月周期才做「上一个自然月」对比
        prev_start = (start.replace(day=1) - timedelta(days=1)).replace(day=1)
        prev_end = start
        if start.day != 1 or (end - start).days < 28:
            return {"status": "not_applicable", "note": "仅自然月周期提供上一月对比"}
        try:
            if ds.is_mock:
                prev_ds = build_mock_dataset(prev_start, prev_end)
                prev_metrics = calculate_customer_stats(prev_ds.customers, prev_start, prev_end)
            else:
                prev_res = await fetch_customers(self.repo.db, prev_start, prev_end)
                prev_metrics = calculate_customer_stats(prev_res.inputs, prev_start, prev_end)
        except Exception as exc:  # noqa: BLE001 — 对比失败不影响主报告
            logger.warning("M5 上一周期对比取数失败: %s", exc)
            return {"status": "unavailable", "period_start": prev_start.isoformat(),
                    "period_end": prev_end.isoformat(), "note": "上一周期数据不可得，不做对比"}
        if prev_metrics.get("availability", {}).get("status") != "ok":
            return {"status": "unavailable", "period_start": prev_start.isoformat(),
                    "period_end": prev_end.isoformat(),
                    "note": "上一周期期末状态不可得，无法对比（不当作零）"}
        return {
            "status": "ok",
            "period_start": prev_start.isoformat(),
            "period_end": prev_end.isoformat(),
            "metrics": {"new_this_period": prev_metrics.get("new_this_period"),
                        "status_overview": prev_metrics.get("status_overview")},
        }

    async def get_report(self, report_id: int) -> AiReport:
        report = await self.repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="报告不存在")
        return report

    async def list_reports(self, report_type: str | None, page: int, page_size: int) -> tuple[list[AiReport], int]:
        return await self.repo.list_latest(report_type, page, page_size)

    async def _save_drill_snapshot(
        self, report: AiReport, ds: MockReportDataset, start: datetime, end: datetime
    ) -> None:
        """生成时固化授权下钻数据（v6.11.0 §2.2/§五）。

        旧报告的详情/下钻/PDF 之后只读快照，源数据变化或 AI 补分析都不再影响它。
        快照写入失败不阻断报告生成，但要在日志里留痕（下钻会提示无快照）。
        """
        try:
            db = getattr(self.repo, "db", None)
            if db is None:  # 单测里的轻量仓储桩没有 db，跳过快照
                return
            rows: list[tuple[str, list[dict]]] = []
            if report.report_type == "customer_analysis":
                rows.append(("customers", customer_drilldown(ds)))
            elif report.report_type == "psych_weekly":
                rows.append(("psych_cases", psych_cases_snapshot(ds, start, end)))
            elif report.report_type == "complaint_weekly":
                rows.append(("special_cases", special_cases_snapshot(ds)))
            for drill_type, payload in rows:
                db.add(AiReportDrill(
                    report_id=report.id,
                    drill_type=drill_type,
                    payload=payload,
                    row_count=len(payload),
                ))
            if rows:
                await db.commit()
        except Exception as exc:  # noqa: BLE001 — 快照失败不倒扣报告本身
            logger.warning("M5 下钻快照写入失败: report_id=%s error=%s", report.id, exc)

    async def _read_drill(self, report_id: int, drill_type: str) -> tuple[list[dict], str]:
        """读下钻快照。历史报告无快照时返回空 + 明确提示，**不回查实时数据**。"""
        db = getattr(self.repo, "db", None)
        if db is None:
            return [], "该版本无下钻快照（历史报告），按快照口径不回查实时数据"
        row = (await db.execute(
            select(AiReportDrill).where(
                AiReportDrill.report_id == report_id,
                AiReportDrill.drill_type == drill_type,
            ).order_by(AiReportDrill.id.desc()).limit(1)
        )).scalars().first()
        if row is None:
            return [], "该版本无下钻快照（历史报告），按快照口径不回查实时数据"
        return list(row.payload or []), ""

    async def customer_drilldown(self, report_id: int) -> tuple[list[dict], str]:
        report = await self.get_report(report_id)
        if report.report_type != "customer_analysis":
            raise ValidationError(message="客户下钻仅适用于客户经营分析报告")
        return await self._read_drill(report.id, "customers")

    async def psych_cases(self, report_id: int, user: User) -> tuple[list[dict], str]:
        report = await self.get_report(report_id)
        if report.report_type != "psych_weekly":
            raise ValidationError(message="心理个案仅适用于心理周报")
        cases, note = await self._read_drill(report.id, "psych_cases")
        return filter_psych_cases(cases, user), note

    async def special_cases(self, report_id: int) -> tuple[list[dict], str]:
        report = await self.get_report(report_id)
        if report.report_type != "complaint_weekly":
            raise ValidationError(message="特别案例仅适用于投诉周报")
        return await self._read_drill(report.id, "special_cases")

    async def list_versions(
        self, report_type: str, period_start: datetime, period_end: datetime
    ) -> list[AiReport]:
        """历史版本列表（v6.11.0 §2.1：同类型同周期可查全部历史版本）。"""
        return await self.repo.list_versions(report_type, period_start, period_end)

    async def download_pdf(self, report_id: int) -> bytes:
        report = await self.get_report(report_id)
        # M5-11.5：空内容防护（failed 记录或历史脏数据 report_content 为 None）
        if not report.report_content:
            raise ValidationError(message="报告无内容，无法导出 PDF")
        return generate_report_pdf(report.report_content)
