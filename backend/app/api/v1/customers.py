from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.schemas.customer import (
    CustomerCreate,
    CustomerOut,
    CustomerStatusChange,
    CustomerUpdate,
    MyCustomerOut,
    PendingLeadCreate,
    PendingLeadMerge,
    PendingLeadOut,
)
from app.services.crm_service import CrmService
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["客户管理"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CustomerService:
    repo = CustomerRepository(db)
    crm_service = CrmService(CrmRepository(db), repo)
    return CustomerService(repo, crm_service)


@router.get("", summary="客户列表")
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    owner_id = None
    if current_user.user_type == "EMPLOYEE":
        owner_id = current_user.id
    items, total = await service.list_customers(page, page_size, owner_id, status)
    return success_response(data={"items": [CustomerOut.model_validate(c) for c in items], "total": total, "page": page, "page_size": page_size})


@router.post("", summary="创建客户")
async def create_customer(
    data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    customer = await service.create_customer(data.model_dump(exclude_unset=True))
    return success_response(data=CustomerOut.model_validate(customer), message="创建成功")


@router.post("/pending-leads", summary="创建待补全线索")
async def create_pending_lead(
    data: PendingLeadCreate,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    pending = await service.create_pending_lead(data)
    return success_response(data=PendingLeadOut.model_validate(pending), message="创建成功")


@router.get("/pending-leads", summary="待补全线索列表")
async def list_pending_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    items, total = await service.list_pending_leads(page, page_size)
    return success_response(data={"items": [PendingLeadOut.model_validate(i) for i in items], "total": total, "page": page, "page_size": page_size})


@router.post("/pending-leads/{lead_id}/merge", summary="合并待补全线索为客户")
async def merge_pending_lead(
    lead_id: int,
    data: PendingLeadMerge,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    pending = await service.merge_pending_lead(lead_id, data, current_user)
    return success_response(data=PendingLeadOut.model_validate(pending), message="合并成功")


@router.get("/me", summary="本人客户档案（PROSPECT/STUDENT 自助查询，v6.11.19）")
async def get_my_customer(
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    customer, convert_status = await service.get_my_customer(current_user)
    data = MyCustomerOut.model_validate(customer)
    data.convert_status = convert_status
    return success_response(data=data)


@router.get("/{customer_id}", summary="客户详情")
async def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    customer = await service.get_customer(customer_id)
    return success_response(data=CustomerOut.model_validate(customer))


@router.put("/{customer_id}", summary="更新客户")
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    customer = await service.update_customer(customer_id, data.model_dump(exclude_unset=True))
    return success_response(data=CustomerOut.model_validate(customer), message="更新成功")


@router.patch("/{customer_id}/status", summary="客户 6 态流转")
async def change_customer_status(
    customer_id: int,
    data: CustomerStatusChange,
    current_user: User = Depends(get_current_user),
    service: CustomerService = Depends(_get_service),
):
    customer = await service.change_status(customer_id, data.status)
    return success_response(data=CustomerOut.model_validate(customer), message="状态更新成功")
