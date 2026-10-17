from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.customer_repo import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["客户管理"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CustomerService:
    repo = CustomerRepository(db)
    return CustomerService(repo)


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
