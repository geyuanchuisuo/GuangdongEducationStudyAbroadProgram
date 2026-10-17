import json
import logging
import re
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BusinessError
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.crm import CrmLeadCreate
from app.services.crm_service import CrmService
from app.services.dify_client import DifyClient

logger = logging.getLogger(__name__)

# 客服单会话用户消息轮数上限，超过则归档旧会话并开启新会话（防止 Dify 上下文无限增长）
MAX_TURNS = 10
# 高意向转线索：从用户消息中提取大陆手机号
PHONE_RE = re.compile(r"1[3-9]\d{9}")
# Dify 输出约定标记（前向兼容，未输出时自动跳过）
INTENT_RE = re.compile(r"\[intent:([^\]]+)\]")
RECOMMEND_MARKER = "[RECOMMEND]"


class AiService:
    """智能客服：查/建会话 → 存用户消息 → 调 Dify → 存助手消息，返回答案。

    说明：一期按 Dify 原生 /chat-messages(blocking) 协议实现（对齐 docs/项目需求文档.md §12.3）。
    4 出口：
      阶段1 意图落库（[intent:xxx] 标记 / dify intent 字段 → cs_intent_log）
      阶段2 多轮上限（MAX_TURNS，超限归档旧会话+开新会话）
      阶段3 高意向转线索（提手机号 → create_lead(source="客服") → 回填 session.customer_id）
      阶段4 推荐（[RECOMMEND]{json} 标记 → card_data + recommendations）
    """

    MAX_TURNS = MAX_TURNS

    def __init__(
        self,
        repo: CustomerServiceRepository,
        dify: DifyClient | None = None,
        crm_service: CrmService | None = None,
    ):
        self.repo = repo
        self.dify = dify or DifyClient()
        self.crm_service = crm_service

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not settings.DIFY_CUSTOMER_AGENT_KEY:
            raise BusinessError(code=50001, message="客服 Agent 未配置（DIFY_CUSTOMER_AGENT_KEY 为空）")

        session = await self._get_or_create_session(request)

        # 阶段2：多轮上限——超过上限归档旧会话并开启新会话
        user_turns = await self.repo.count_messages(session.id, role="user")
        if user_turns >= self.MAX_TURNS:
            session.status = "archived"
            await self.repo.update_session(session)
            session = await self.repo.create_session(request.user_id)

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
        intent = dify_resp.get("intent")
        if dify_resp.get("conversation_id"):
            session.dify_conversation_id = dify_resp["conversation_id"]
            await self.repo.update_session(session)

        # 阶段1：意图标记剥离（优先 [intent:xxx]，其次 dify intent 字段）
        answer, intent_marker = self._extract_intent(answer)
        intent = intent_marker or intent

        # 阶段4：推荐标记剥离 → card_data + recommendations
        answer, recommendations = self._extract_recommendations(answer)
        card_data = {"recommendations": recommendations} if recommendations else None

        # 阶段3：高意向转线索——从用户消息提取手机号并建档（回填 session.customer_id）
        converted = False
        customer_id = session.customer_id
        phone = self._extract_phone(request.message)
        if phone and self.crm_service and not session.customer_id:
            try:
                lead_result = await self.crm_service.create_lead(
                    CrmLeadCreate(phone=phone, source="客服", raw_input=request.message),
                    None,
                )
                customer_id = lead_result["lead"]["customer_id"]
                session.customer_id = customer_id
                await self.repo.update_session(session)
                converted = True
            except Exception:
                logger.exception("客服会话转线索失败")

        if intent:
            await self.repo.add_intent_log(
                session.id,
                request.user_id,
                customer_id,
                intent,
                converted=converted,
            )

        await self.repo.add_message(
            session.id, role="assistant", content=answer, intent=intent, card_data=card_data
        )
        return ChatResponse(
            answer=answer,
            conversation_id=str(session.id),
            intent=intent,
            recommendations=recommendations,
        )

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

    @staticmethod
    def _extract_phone(text: str) -> str | None:
        match = PHONE_RE.search(text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_intent(answer: str) -> tuple[str, str | None]:
        match = INTENT_RE.search(answer)
        if not match:
            return answer, None
        cleaned = (answer[: match.start()] + answer[match.end() :]).strip()
        return cleaned, match.group(1).strip()

    @staticmethod
    def _extract_recommendations(answer: str) -> tuple[str, list[dict] | None]:
        idx = answer.find(RECOMMEND_MARKER)
        if idx == -1:
            return answer, None
        before = answer[:idx]
        json_part = answer[idx + len(RECOMMEND_MARKER) :].strip()
        recommendations: list[dict] | None = None
        try:
            parsed = json.loads(json_part)
            recommendations = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            recommendations = None
        return before.strip(), recommendations


# ========================= 通用多 Agent 服务（M3/M4 依赖） =========================


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


class AIService:
    def __init__(self) -> None:
        self._base_url = settings.DIFY_BASE_URL.rstrip("/")
        self._client: httpx.AsyncClient | None = None

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
