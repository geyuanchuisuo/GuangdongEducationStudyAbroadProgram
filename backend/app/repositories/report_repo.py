"""M5 智能报告模块 — 报告仓储。"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import AiReport


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, report: AiReport) -> AiReport:
        """落库报告；版本号唯一约束冲突时（M5-06.4）重取版本号重试一次。"""
        self.db.add(report)
        try:
            await self.db.commit()
        except IntegrityError:
            # 并发下同 (type, start, end, version) 撞唯一约束 uq_ai_report_version
            await self.db.rollback()
            report.id = None
            report.version = await self.next_version(
                report.report_type, report.time_range_start, report.time_range_end
            )
            self.db.add(report)
            await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, report_id: int) -> AiReport | None:
        result = await self.db.execute(select(AiReport).where(AiReport.id == report_id))
        return result.scalar_one_or_none()

    async def next_version(self, report_type: str, start, end) -> int:
        """同类型同周期的下一个版本号（从 1 开始，重复生成递增）。"""
        stmt = select(func.coalesce(func.max(AiReport.version), 0)).where(
            AiReport.report_type == report_type,
            AiReport.time_range_start == start,
            AiReport.time_range_end == end,
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one()) + 1

    async def list_latest(self, report_type: str | None, page: int, page_size: int) -> tuple[list[AiReport], int]:
        """报告列表：同类型同周期只保留最新版本。"""
        stmt = select(AiReport).order_by(AiReport.created_at.desc(), AiReport.id.desc())
        if report_type:
            stmt = stmt.where(AiReport.report_type == report_type)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        latest: dict[tuple, AiReport] = {}
        for r in rows:
            key = (r.report_type, r.time_range_start, r.time_range_end)
            latest.setdefault(key, r)

        items = list(latest.values())
        total = len(items)
        return items[(page - 1) * page_size: page * page_size], total

    async def list_versions(
        self, report_type: str, period_start, period_end
    ) -> list[AiReport]:
        """同类型同周期的全部历史版本（v6.11.0 §2.1：历史版本可查、不覆盖）。"""
        stmt = (
            select(AiReport)
            .where(
                AiReport.report_type == report_type,
                AiReport.time_range_start == period_start,
                AiReport.time_range_end == period_end,
            )
            .order_by(AiReport.version.desc(), AiReport.id.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())
