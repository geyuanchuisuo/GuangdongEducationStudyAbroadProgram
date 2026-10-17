import json
import logging
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BusinessError
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest, ChatResponse
from app.services.dify_client import DifyClient

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    CUSTOMER = "CUSTOMER"
    EMPLOYEE = "EMPLOYEE"
    STUDENT = "STUDENT"


class AIResponse:
    def __init__(self, content: str, session_id: str, usage: dict | None = None, raw: dict | None = None):
        self.content = content
        self.session_id = session_id
        self.usage = usage or {}
        self.raw = raw or {}


_AGENT_KEY_MAP: dict[AgentType, str] = {
    AgentType.CUSTOMER: settings.DIFY_CUSTOMER_AGENT_KEY,
    AgentType.EMPLOYEE: settings.DIFY_EMPLOYEE_AGENT_KEY,
    AgentType.STUDENT: settings.DIFY_STUDENT_AGENT_KEY,
}

_TIMEOUT = 60.0
_MAX_RETRIES = 2
class AiService:
    def __init__(self, repo: CustomerServiceRepository, dify: DifyClient | None = None):
        self.repo = repo
        self.dify = dify or DifyClient()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not settings.DIFY_CUSTOMER_AGENT_KEY:
            raise BusinessError(code=50001, message="客服 Agent 未配置（DIFY_CUSTOMER_AGENT_KEY 为空）")

class AIService:
    def __init__(self) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        session = await self._get_or_create_session(request)
        await self.repo.add_message(session.id, role="user", content=request.message)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._client

    def _get_api_key(self, agent: AgentType) -> str:
        key = _AGENT_KEY_MAP.get(agent, "")
        if not key:
            raise ValueError(f"Dify API key not configured for agent type: {agent.value}")
        return key

    def _build_headers(self, agent: AgentType) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_api_key(agent)}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        agent: AgentType,
        message: str,
        session_id: str,
        user_id: str = "default",
        context: dict[str, Any] | None = None,
    ) -> AIResponse:
        client = await self._get_client()
        payload: dict[str, Any] = {
            "inputs": context or {},
            "query": message,
            "response_mode": "blocking",
            "user": user_id,
        }
        if session_id and session_id != "new":
            payload["conversation_id"] = session_id

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.post(
                    f"{self._base_url}/v1/chat-messages",
                    headers=self._build_headers(agent),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        try:
            dify_resp = await self.dify.chat(
                query=request.message,
                user=str(request.user_id or "anonymous"),
                conversation_id=session.dify_conversation_id,
            )
        except httpx.HTTPError as exc:
            raise BusinessError(code=50001, message=f"客服 Agent 服务不可用：{type(exc).__name__}")

                return AIResponse(
                    content=data.get("answer", ""),
                    session_id=data.get("conversation_id", session_id),
                    usage=data.get("metadata", {}).get("usage", {}),
                    raw=data,
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_error = exc
                logger.warning(
                    "AI chat attempt %d/%d failed: agent=%s error=%s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    agent.value,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    continue
        answer = dify_resp.get("answer") or ""
        intent = dify_resp.get("intent")  # Dify 工作流若输出 intent 字段则记录
        if dify_resp.get("conversation_id"):
            session.dify_conversation_id = dify_resp["conversation_id"]
            await self.repo.update_session(session)

        logger.error("AI chat all retries exhausted: agent=%s", agent.value)
        raise last_error  # type: ignore[misc]
        await self.repo.add_message(session.id, role="assistant", content=answer, intent=intent)
        return ChatResponse(answer=answer, conversation_id=str(session.id), intent=intent)

    async def chat_stream(
        self,
        agent: AgentType,
        message: str,
        session_id: str,
        user_id: str = "default",
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        client = await self._get_client()
        payload: dict[str, Any] = {
            "inputs": context or {},
            "query": message,
            "response_mode": "streaming",
            "user": user_id,
        }
        if session_id and session_id != "new":
            payload["conversation_id"] = session_id

        async with client.stream(
            "POST",
            f"{self._base_url}/v1/chat-messages",
            headers=self._build_headers(agent),
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    event = chunk.get("event", "")
                    if event == "message" or event == "agent_message":
                        token = chunk.get("answer", "")
                        if token:
                            yield token
                except json.JSONDecodeError:
                    logger.debug("Skipping non-JSON SSE line: %s", data_str[:100])

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


ai_service = AIService()
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
