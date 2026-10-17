import re

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.models.customer import Customer
from app.repositories.customer_repo import CustomerRepository

PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


class CustomerService:
    def __init__(self, repo: CustomerRepository):
        self.repo = repo

    async def create_customer(self, data: dict) -> Customer:
        phone = data.get("phone")
        if not phone or not PHONE_REGEX.match(phone):
            raise BusinessError(code=40002, message="手机号不合规，需1开头11位大陆手机号")

        existing = await self.repo.get_by_phone(phone)
        if existing:
            raise ConflictError(message=f"手机号 {phone} 已存在")

        customer = Customer(**data, status="NEW", phone_status="normal")
        return await self.repo.create(customer)

    async def get_customer(self, customer_id: int) -> Customer:
        customer = await self.repo.get_by_id(customer_id)
        if not customer:
            raise NotFoundError(message="客户不存在")
        return customer

    async def update_customer(self, customer_id: int, data: dict) -> Customer:
        customer = await self.get_customer(customer_id)
        if "phone" in data and data["phone"]:
            phone = data["phone"]
            if not PHONE_REGEX.match(phone):
                raise BusinessError(code=40002, message="手机号不合规")
            existing = await self.repo.get_by_phone(phone)
            if existing and existing.id != customer_id:
                raise ConflictError(message=f"手机号 {phone} 已被其他客户使用")
        return await self.repo.update(customer, data)

    async def list_customers(self, page: int = 1, page_size: int = 20, owner_employee_id: int | None = None, status: str | None = None) -> tuple[list[Customer], int]:
        if owner_employee_id:
            return await self.repo.list_by_owner(owner_employee_id, page, page_size)
        return await self.repo.list_all(page, page_size, status)
