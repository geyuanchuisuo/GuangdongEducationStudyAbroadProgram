import re

from app.core.exceptions import BusinessError, ConflictError, NotFoundError, ValidationError
from app.models.customer import Customer, PendingLead
from app.models.user import User
from app.repositories.customer_repo import CustomerRepository
from app.schemas.crm import CrmLeadCreate
from app.schemas.customer import PendingLeadCreate, PendingLeadMerge
from app.services.crm_service import CrmService

PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")

# 客户 6 态状态机（对齐接口契约 §0.5，英文编码为 M1 标准存储值）
CUSTOMER_STATUSES = ("NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST")
CUSTOMER_STATUS_TRANSITIONS = {
    "NEW": ("FOLLOWING", "LOST"),
    "FOLLOWING": ("STRONG", "LOST"),
    "STRONG": ("SIGNED", "LOST"),
    "SIGNED": ("ENROLLED", "LOST"),
    "ENROLLED": ("LOST",),
    "LOST": ("FOLLOWING",),
}
# 中文状态值归一化到英文编码（兼容 M3 写入的中文值与历史英文编码）
STATUS_CN_TO_EN = {
    "新录入": "NEW",
    "跟进中": "FOLLOWING",
    "意向强烈": "STRONG",
    "已签约": "SIGNED",
    "已入学": "ENROLLED",
    "已流失": "LOST",
    "CONVERTED": "SIGNED",
}


class CustomerService:
    def __init__(self, repo: CustomerRepository, crm_service: CrmService | None = None):
        self.repo = repo
        self.crm_service = crm_service

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

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        if not status:
            return "NEW"
        return STATUS_CN_TO_EN.get(status, status)

    async def change_status(self, customer_id: int, target: str) -> Customer:
        customer = await self.get_customer(customer_id)
        target_en = self._normalize_status(target)
        if target_en not in CUSTOMER_STATUSES:
            raise ValidationError(message=f"非法状态：{target}")
        current_en = self._normalize_status(customer.status)
        allowed = CUSTOMER_STATUS_TRANSITIONS.get(current_en, ())
        if target_en not in allowed:
            raise ValidationError(message=f"状态不能从「{current_en}」流转到「{target_en}」，允许：{allowed}")
        return await self.repo.update(customer, {"status": target_en})

    # ── 待补全线索（pending_lead） ──────────────────────────
    async def create_pending_lead(self, data: PendingLeadCreate) -> PendingLead:
        pending = PendingLead(
            wechat=data.wechat,
            name=data.name,
            raw_info=data.raw_info,
            source_session_id=data.source_session_id,
            status="pending",
        )
        return await self.repo.create_pending_lead(pending)

    async def list_pending_leads(self, page: int = 1, page_size: int = 20) -> tuple[list[PendingLead], int]:
        return await self.repo.list_pending_leads(page, page_size)

    async def merge_pending_lead(self, lead_id: int, data: PendingLeadMerge, current_user: User | None = None) -> PendingLead:
        pending = await self.repo.get_pending_lead(lead_id)
        if not pending:
            raise NotFoundError(message="待补全线索不存在")
        if pending.status == "merged":
            raise ConflictError(message="该待补全线索已合并")
        if not self.crm_service:
            raise BusinessError(code=50001, message="客服建档服务未初始化")
        lead_result = await self.crm_service.create_lead(
            CrmLeadCreate(
                phone=data.phone,
                name=data.name,
                gender=data.gender,
                age=data.age,
                education=data.education,
                source="待补全",
                raw_input=pending.raw_info,
            ),
            current_user,
        )
        customer_id = lead_result["lead"]["customer_id"]
        return await self.repo.update_pending_lead(
            pending, {"merged_customer_id": customer_id, "status": "merged"}
        )
