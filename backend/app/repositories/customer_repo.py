from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, PendingLead
from app.models.system import ApprovalInstance


class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, customer_id: int) -> Customer | None:
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()

    async def get_by_sys_user_id(self, sys_user_id: int) -> Customer | None:
        result = await self.db.execute(select(Customer).where(Customer.sys_user_id == sys_user_id))
        return result.scalar_one_or_none()

    async def get_latest_convert_status(self, customer_id: int) -> str | None:
        """只读查 approval_instance 表最新一条 convert 审批状态（v6.11.19，M1 只读 M0 表）。"""
        stmt = (
            select(ApprovalInstance.status)
            .where(ApprovalInstance.biz_type == "convert", ApprovalInstance.biz_id == customer_id)
            .order_by(ApprovalInstance.created_at.desc(), ApprovalInstance.id.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Customer | None:
        result = await self.db.execute(select(Customer).where(Customer.phone == phone))
        return result.scalar_one_or_none()

    async def create(self, customer: Customer) -> Customer:
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def update(self, customer: Customer, data: dict) -> Customer:
        for key, value in data.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def list_by_owner(self, owner_employee_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Customer], int]:
        stmt = select(Customer).where(Customer.owner_employee_id == owner_employee_id)
        count_stmt = select(Customer.id).where(Customer.owner_employee_id == owner_employee_id)

        total_result = await self.db.execute(count_stmt)
        total = len(total_result.all())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(Customer.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all(self, page: int = 1, page_size: int = 20, status: str | None = None) -> tuple[list[Customer], int]:
        stmt = select(Customer)
        count_stmt = select(Customer.id)
        if status:
            stmt = stmt.where(Customer.status == status)
            count_stmt = count_stmt.where(Customer.status == status)

        total_result = await self.db.execute(count_stmt)
        total = len(total_result.all())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(Customer.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # ── 待补全线索（pending_lead） ──────────────────────────
    async def create_pending_lead(self, pending: PendingLead) -> PendingLead:
        self.db.add(pending)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending

    async def get_pending_lead(self, lead_id: int) -> PendingLead | None:
        result = await self.db.execute(select(PendingLead).where(PendingLead.id == lead_id))
        return result.scalar_one_or_none()

    async def list_pending_leads(self, page: int = 1, page_size: int = 20) -> tuple[list[PendingLead], int]:
        stmt = select(PendingLead).where(PendingLead.status == "pending")
        count_stmt = select(PendingLead.id).where(PendingLead.status == "pending")

        total_result = await self.db.execute(count_stmt)
        total = len(total_result.all())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(PendingLead.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_pending_lead(self, pending: PendingLead, data: dict) -> PendingLead:
        for key, value in data.items():
            if hasattr(pending, key):
                setattr(pending, key, value)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending
