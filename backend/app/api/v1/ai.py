import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.database import get_db
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.repositories.event_repo import EventRepository
from app.repositories.user_repo import UserRepository
from app.schemas.ai import ChatRequest
from app.services.cs_agent_service import AiService
from app.services.crm_service import CrmService
from app.services.event_service import EventService

router = APIRouter(prefix="/ai", tags=["智能客服"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AiService:
    repo = CustomerServiceRepository(db)
    customer_repo = CustomerRepository(db)
    crm_service = CrmService(CrmRepository(db), customer_repo)
    event_service = EventService(EventRepository(db))
    user_repo = UserRepository(db)
    return AiService(
        repo,
        crm_service=crm_service,
        customer_repo=customer_repo,
        event_service=event_service,
        user_repo=user_repo,
    )


@router.post("/customer-service/chat")
async def customer_service_chat(request: ChatRequest, service: AiService = Depends(_get_service)):
    result = await service.chat(request)
    return success_response(data=result.model_dump())


@router.post("/customer-service/chat/stream")
async def customer_service_chat_stream(request: ChatRequest, service: AiService = Depends(_get_service)):
    """流式客服对话（SSE）：event: meta / token / done。

    v6.11.37：感知延迟=首字时间（token 增量下发）；done 事件携带与
    POST /customer-service/chat 相同结构的最终数据（intent/recommendations/card_data）。
    流式失败由服务层降级链兜底，前端必收 done；调用方也可回退非流式接口。
    """

    async def event_gen():
        async for ev in service.chat_stream(request):
            name = ev.get("event")
            if name == "token":
                payload: dict = {"delta": ev["delta"]}
            elif name == "meta":
                payload = {"conversation_id": ev["conversation_id"]}
            else:
                payload = ev.get("data") or {}
            yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # X-Accel-Buffering: no —— 反代（nginx）据此对该响应禁用缓冲（LOG-097 双保险，
    # 即使 nginx.conf 未关 proxy_buffering 也保证 SSE 增量即时下发）
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
