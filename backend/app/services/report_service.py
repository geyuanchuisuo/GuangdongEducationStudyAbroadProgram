"""M5 智能报告模块 — 报告生成编排服务（阶段 3）

一期数据来源为模拟数据；后续接入真实数据时只替换 provider，
指标计算、内容结构、版本、接口均不变。
"""
from datetime import datetime

from app.core.exceptions import NotFoundError, ValidationError
from app.models.crm import AiReport
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.services.report_ai_service import ReportAIService
from app.services.report_content import REPORT_TYPE_NAMES, build_report_content
from app.services.report_drilldown import (
    customer_drilldown,
    psych_cases_for_user,
    special_cases_drilldown,
)
from app.services.report_mock_data import build_mock_dataset
from app.services.report_pdf import generate_report_pdf


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

        ds = build_mock_dataset()
        start = period_start or ds.period_start
        end = period_end or ds.period_end
        if start >= end:
            raise ValidationError(message="周期起点必须早于终点")

        version = await self.repo.next_version(report_type, start, end)
        content = build_report_content(report_type, ds, start, end, version, datetime.now())

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
        return await self.repo.create(report)

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
        return customer_drilldown(build_mock_dataset())

    async def psych_cases(self, report_id: int, user: User) -> list[dict]:
        report = await self.get_report(report_id)
        if report.report_type != "psych_weekly":
            raise ValidationError(message="心理个案仅适用于心理周报")
        ds = build_mock_dataset()
        start = report.time_range_start or ds.period_start
        end = report.time_range_end or ds.period_end
        return psych_cases_for_user(ds, start, end, user)

    async def special_cases(self, report_id: int) -> list[dict]:
        report = await self.get_report(report_id)
        if report.report_type != "complaint_weekly":
            raise ValidationError(message="特别案例仅适用于投诉周报")
        return special_cases_drilldown(build_mock_dataset())

    async def download_pdf(self, report_id: int) -> bytes:
        report = await self.get_report(report_id)
        return generate_report_pdf(report.report_content)
