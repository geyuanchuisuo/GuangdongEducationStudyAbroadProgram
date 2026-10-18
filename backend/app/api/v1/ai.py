from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.database import get_db
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.ai_service import AiService
from app.services.crm_service import CrmService

router = APIRouter(prefix="/ai", tags=["智能客服"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AiService:
    repo = CustomerServiceRepository(db)
    customer_repo = CustomerRepository(db)
    crm_service = CrmService(CrmRepository(db), customer_repo)
    return AiService(repo, crm_service=crm_service, customer_repo=customer_repo)


@router.post("/customer-service/chat")
async def customer_service_chat(request: ChatRequest, service: AiService = Depends(_get_service)):
    result = await service.chat(request)
    return success_response(data=result.model_dump())
