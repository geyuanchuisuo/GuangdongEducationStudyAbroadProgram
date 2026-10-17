import httpx

from app.config import settings
from app.core.exceptions import BusinessError
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest, ChatResponse
from app.services.dify_client import DifyClient


class AiService:
    def __init__(self, repo: CustomerServiceRepository, dify: DifyClient | None = None):
        self.repo = repo
        self.dify = dify or DifyClient()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not settings.DIFY_CUSTOMER_AGENT_KEY:
            raise BusinessError(code=50001, message="客服 Agent 未配置（DIFY_CUSTOMER_AGENT_KEY 为空）")

        session = await self._get_or_create_session(request)
        await self.repo.add_message(session.id, role="user", content=request.message)

        try:
            dify_resp = await self.dify.chat(
                query=request.message,
                user=str(request.user_id or "anonymous"),
                conversation_id=session.dify_conversation_id,
            )
        except httpx.HTTPError as exc:
            raise BusinessError(code=50001, message=f"客服 Agent 服务不可用：{type(exc).__name__}")

        answer = dify_resp.get("answer") or ""
        intent = dify_resp.get("intent")  # Dify 工作流若输出 intent 字段则记录
        if dify_resp.get("conversation_id"):
            session.dify_conversation_id = dify_resp["conversation_id"]
            await self.repo.update_session(session)

        await self.repo.add_message(session.id, role="assistant", content=answer, intent=intent)
        return ChatResponse(answer=answer, conversation_id=str(session.id), intent=intent)

    async def _get_or_create_session(self, request: ChatRequest):
        session_id: int | None = None
        if request.conversation_id:
            try:
                session_id = int(request.conversation_id)
            except (TypeError, ValueError):
                session_id = None
        if session_id is not None:
            session = await self.repo.get_session(session_id)
            if session:
                return session
        return await self.repo.create_session(request.user_id)
