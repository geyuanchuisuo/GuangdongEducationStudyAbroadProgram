from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, customer_id: int) -> Customer | None:
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
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
