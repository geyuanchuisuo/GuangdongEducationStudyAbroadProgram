from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.database import get_db
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest
from app.services.ai_service import AiService

router = APIRouter(prefix="/ai", tags=["智能客服"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AiService:
    return AiService(CustomerServiceRepository(db))


@router.post("/customer-service/chat")
async def customer_service_chat(request: ChatRequest, service: AiService = Depends(_get_service)):
    result = await service.chat(request)
    return success_response(data=result.model_dump())
