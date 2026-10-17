"""M5 智能报告模块 — 报告仓储。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import AiReport


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, report: AiReport) -> AiReport:
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
