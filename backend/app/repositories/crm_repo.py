from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import CrmFollowUp, CrmLead, CustomerAssessment


class CrmRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead(self, lead_id: int) -> CrmLead | None:
        result = await self.db.execute(select(CrmLead).where(CrmLead.id == lead_id))
        return result.scalar_one_or_none()

    async def list_leads(
        self,
        page: int,
        page_size: int,
        owner_employee_id: int | None = None,
        status: str | None = None,
    ) -> tuple[int, list[CrmLead]]:
        query = select(CrmLead)
        count_query = select(func.count(CrmLead.id))
        if owner_employee_id is not None:
            query = query.where(CrmLead.owner_employee_id == owner_employee_id)
            count_query = count_query.where(CrmLead.owner_employee_id == owner_employee_id)
        if status is not None:
            query = query.where(CrmLead.status == status)
            count_query = count_query.where(CrmLead.status == status)
        query = query.order_by(CrmLead.id.desc()).offset((page - 1) * page_size).limit(page_size)
        total = (await self.db.execute(count_query)).scalar_one()
        items = (await self.db.execute(query)).scalars().all()
        return total, list(items)

    async def create_lead(self, lead: CrmLead) -> CrmLead:
        self.db.add(lead)
        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    async def update_lead(self, lead: CrmLead) -> CrmLead:
        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    async def list_assessments(self, page: int, page_size: int) -> tuple[int, list[CustomerAssessment]]:
        query = (
            select(CustomerAssessment)
            .order_by(CustomerAssessment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = (await self.db.execute(select(func.count(CustomerAssessment.id)))).scalar_one()
        items = (await self.db.execute(query)).scalars().all()
        return total, list(items)

    async def get_assessment(self, assessment_id: int) -> CustomerAssessment | None:
        result = await self.db.execute(select(CustomerAssessment).where(CustomerAssessment.id == assessment_id))
        return result.scalar_one_or_none()

    async def create_assessment(self, assessment: CustomerAssessment) -> CustomerAssessment:
        self.db.add(assessment)
        await self.db.commit()
        await self.db.refresh(assessment)
        return assessment

    async def create_follow_up(self, follow_up: CrmFollowUp) -> CrmFollowUp:
        self.db.add(follow_up)
        await self.db.commit()
        await self.db.refresh(follow_up)
        return follow_up
