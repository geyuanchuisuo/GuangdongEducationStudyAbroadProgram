"""M0 通用多 Agent AI 网关（v6.10.2 模块解耦后回归纯 M0 职责）。

v6.8.8~v6.10.1 期间本文件为「M0 通用 AIService + M2 客服 AiService」双服务共存；
v6.10.2 M2 客服 AiService 已迁出至 app/services/cs_agent_service.py（逻辑不变），
M3/M4 依赖的通用符号（AgentType/AIResponse/AIService/ai_service）保持原位原实现，
调用方式零改动：`from app.services.ai_service import AgentType, ai_service`。
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    CUSTOMER = "CUSTOMER"
    EMPLOYEE = "EMPLOYEE"
    STUDENT = "STUDENT"
    REPORT = "REPORT"


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
    AgentType.REPORT: settings.DIFY_REPORT_AGENT_KEY,
}

_MAX_RETRIES = 2
# 重试等待：指数退避 1s → 2s（上限 8s）；429 优先服从响应头 Retry-After
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 8.0
# 确定性错误：重试必然同样失败，立即放弃，避免白等「超时 × 尝试次数」
# （如 key 失效 401、应用已被删除 404、请求体非法 400）
_NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404, 405, 409, 422})


class AIService:
    def __init__(self) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._timeout = settings.DIFY_AI_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
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

    @staticmethod
    def _retry_delay(attempt: int, exc: Exception) -> float:
        """重试等待秒数：优先服从 429 的 Retry-After，否则指数退避（1s → 2s，上限 8s）。"""
        if isinstance(exc, httpx.HTTPStatusError):
            retry_after = exc.response.headers.get("Retry-After", "").strip()
            if retry_after.isdigit():
                return min(float(retry_after), _BACKOFF_MAX)
        return min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_MAX)

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

                return AIResponse(
                    content=data.get("answer", ""),
                    session_id=data.get("conversation_id", session_id),
                    usage=data.get("metadata", {}).get("usage", {}),
                    raw=data,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                logger.warning(
                    "AI chat attempt %d/%d failed: agent=%s status=%s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    agent.value,
                    status,
                )
                # 确定性错误（key 错/应用不存在/请求非法）重试也必然失败，立即放弃
                if status in _NON_RETRYABLE_STATUS:
                    logger.error(
                        "AI chat 命中确定性错误，不再重试: agent=%s status=%s",
                        agent.value,
                        status,
                    )
                    break
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(self._retry_delay(attempt, exc))
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "AI chat attempt %d/%d failed: agent=%s error=%s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    agent.value,
                    exc,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(self._retry_delay(attempt, exc))

        logger.error("AI chat all retries exhausted: agent=%s", agent.value)
        raise last_error  # type: ignore[misc]

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
