"""M5 智能报告模块 — 报告生成编排服务（阶段 3 + 批次 C 生产取数）

数据来源由 settings.REPORT_DATA_SOURCE 开关选择（M5-02.3）：
- mock（默认）：模拟数据提供器，参考周期为固定演示周期；
- production：真实业务适配器（report_data_source.py），缺数据显式标记，
  必取域不可用直接拒绝生成，禁止回落 mock（M5-02.4）。
指标计算、内容结构、版本、接口均不随 provider 变化。
"""
from datetime import datetime

from app.config import settings
from app.core.exceptions import BusinessError, NotFoundError, ValidationError
from app.models.crm import AiReport
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.schemas.report import MockReportDataset
from app.services.report_ai_service import ReportAIService
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
    psych_cases_for_user,
    special_cases_drilldown,
)
from app.services.report_mock_data import build_mock_dataset
from app.services.report_pdf import generate_report_pdf
from app.utils.report_period import PeriodValidationError, validate_period, week_range

_MAX_ATTEMPTS = 2  # M5-12.2：生成失败自动重试一次，仍失败落 failed 记录

# 报告类型 → 生成所需的（复数）数据域
_REQUIRED_DOMAINS: dict[str, tuple[str, ...]] = {
    "customer_analysis": ("customers",),
    "daily_report_summary": ("employees", "daily_reports"),
    "weekly_report_summary": ("employees", "daily_reports"),
    "psych_weekly": ("psych",),
    "complaint_weekly": ("complaints",),
}


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

        # M5-02.3 provider 开关：production 走真实适配器（禁回落 mock），mock 走模拟数据
        if settings.REPORT_DATA_SOURCE == "production":
            ds, data_quality, extra_notes = await self._build_production_dataset(
                report_type, period_start, period_end
            )
        else:
            ds = build_mock_dataset(period_start, period_end)
            data_quality, extra_notes = None, None
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
                )
                # 阶段 5：AI 只写文字，失败不阻断确定性统计
                analysis = await self.ai.analyze(report_type, content["metrics"])
                if analysis:
                    content.update(analysis)
                    content["ai_status"] = "available"
                else:
                    content["ai_status"] = "unavailable"

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
                return await self.repo.create(report)
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
    ) -> tuple[MockReportDataset, dict, list[str]]:
        """生产取数（M5-02.1/02.4/02.5）：逐域适配、失败显式标记、必取域不可用则拒绝生成。

        周期缺省 = 当前自然周（生产模式不依赖 mock 参考周期）。
        """
        db = self.repo.db
        start = period_start or week_range(datetime.now())[0]
        end = period_end or week_range(datetime.now())[1]
        data_quality: dict[str, str] = {}
        notes: list[str] = []

        customers_res = psych_res = None
        emp_res = rep_res = None
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
        complaints_res = await fetch_complaints(db, start, end)  # data_unavailable，不抛

        for name, res in (("customers", customers_res), ("employees", emp_res),
                          ("daily_reports", rep_res), ("psych", psych_res),
                          ("complaints", complaints_res)):
            if res is None:
                continue
            data_quality[name] = res.status
            if res.note:
                notes.append(res.note)

        # 必取域不可用 → 拒绝生成（M5-02.4：禁止产出"像真的"的空报告）
        bad = [d for d in _REQUIRED_DOMAINS[report_type] if data_quality.get(d) not in ("ok", "empty")]
        if bad:
            raise ValidationError(
                message=f"无法生成真实数据报告：所需数据域不可用（{', '.join(bad)}）——"
                        f"详见数据质量标注，不回落模拟数据"
            )

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
        return ds, data_quality, notes

    async def get_report(self, report_id: int) -> AiReport:
        report = await self.repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="报告不存在")
        return report

    async def list_reports(self, report_type: str | None, page: int, page_size: int) -> tuple[list[AiReport], int]:
        return await self.repo.list_latest(report_type, page, page_size)

    async def customer_drilldown(self, report_id: int) -> list[dict]:
        report = await self.get_report(report_id)
        if report.report_type != "customer_analysis":
            raise ValidationError(message="客户下钻仅适用于客户经营分析报告")
        ds = build_mock_dataset(report.time_range_start, report.time_range_end)
        return customer_drilldown(ds)

    async def psych_cases(self, report_id: int, user: User) -> list[dict]:
        report = await self.get_report(report_id)
        if report.report_type != "psych_weekly":
            raise ValidationError(message="心理个案仅适用于心理周报")
        ds = build_mock_dataset(report.time_range_start, report.time_range_end)
        start = report.time_range_start or ds.period_start
        end = report.time_range_end or ds.period_end
        return psych_cases_for_user(ds, start, end, user)

    async def special_cases(self, report_id: int) -> list[dict]:
        report = await self.get_report(report_id)
        if report.report_type != "complaint_weekly":
            raise ValidationError(message="特别案例仅适用于投诉周报")
        ds = build_mock_dataset(report.time_range_start, report.time_range_end)
        return special_cases_drilldown(ds)

    async def download_pdf(self, report_id: int) -> bytes:
        report = await self.get_report(report_id)
        # M5-11.5：空内容防护（failed 记录或历史脏数据 report_content 为 None）
        if not report.report_content:
            raise ValidationError(message="报告无内容，无法导出 PDF")
        return generate_report_pdf(report.report_content)
