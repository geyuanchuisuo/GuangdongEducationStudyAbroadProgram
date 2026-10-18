import json
import logging
import re
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BusinessError
from app.models.customer import PendingLead
from app.repositories.customer_repo import CustomerRepository
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
# 微信号提取：仅匹配显式关键词后跟 6-20 位字母开头的账号（防误伤普通英文单词）
WECHAT_RE = re.compile(r"(?:微信号|微信|vx|weixin|wechat)\s*[:：]?\s*([a-zA-Z][a-zA-Z0-9_-]{5,19})", re.IGNORECASE)
# Dify 输出约定标记（前向兼容，未输出时自动跳过）
INTENT_RE = re.compile(r"\[intent:([^\]]+)\]")
RECOMMEND_MARKER = "[RECOMMEND]"
SLOTS_MARKER = "[SLOTS]"
# reasoning 模型思考块（<think>...</think>，含 <!--dify-deepseek-reasoning--> 注释），解析标记前先剥离
THINK_RE = re.compile(r"<think>.*?</think>\s*|<!--[^>]*reasoning[^>]*-->", re.DOTALL | re.IGNORECASE)

# 本地信息提取兜底：当 Dify 未输出 [SLOTS] 时，从用户消息提取常见画像字段
# 每条规则按优先级排列，命中即停；值需通过 _normalize_slot_value 清洗
LOCAL_EXTRACT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "name": [
        re.compile(r"(?:我叫|我是|名字是|姓名是?)\s*([一-龥]{2,4})"),
        re.compile(r"([一-龥]{2,4})(?:同学|您好|你好)"),
    ],
    "age": [
        re.compile(r"(?:今年|年龄|岁)\s*(\d{1,2})\s*岁?"),
        re.compile(r"(\d{1,2})\s*岁"),
    ],
    "education": [
        re.compile(r"(?:学历|在读|年级)\s*[:：]?\s*(初中|高中|高一|高二|高三|本科|大专|硕士|博士|大学)"),
        re.compile(r"(高一|高二|高三|初三|初二|初一|大一|大二|大三|大四|研一|研二|研三)"),
    ],
    "gender": [
        re.compile(r"(?:性别|我是)\s*[:：]?\s*(男|女)"),
    ],
    "study_intent": [
        re.compile(r"(?:想去|意向|目标国家|留学国家)\s*[:：]?\s*(新加坡|德国|美国|英国|澳大利亚|加拿大|日本|韩国|香港|澳门)"),
    ],
}

# 客服对话槽位 → 客户画像字段白名单（与 customer 表列对齐；phone/wechat 单独处理）
PROFILE_SLOT_FIELDS = (
    "name",
    "gender",
    "age",
    "education",
    "economy",
    "needs",
    "study_intent",
    "german_ability",
    "english_ability",
    "closed_training",
    "criminal_record",
    "belt_and_road",
)


class AiService:
    """智能客服：查/建会话 → 存用户消息 → 调 Dify → 存助手消息，返回答案。

    说明：一期按 Dify 原生 /chat-messages(blocking) 协议实现（对齐 docs/项目需求文档.md §12.3）。
    4 出口：
      阶段1 意图落库（[intent:xxx] 标记 / dify intent 字段 → cs_intent_log）
      阶段2 多轮上限（MAX_TURNS，超限归档旧会话+开新会话）
      阶段3 高意向转线索（提手机号 → create_lead(source="客服") → 回填 session.customer_id；
            仅微信号无手机号 → pending_lead 待补全线索，同号去重）
      阶段4 推荐（[RECOMMEND]{json} 标记 → card_data + recommendations + cs_recommend_log 落库）
    信息采集：[SLOTS]{json} 槽位标记 → slots_json 留档 + 转线索建档携带画像 / 老客户画像更新（信息更新不重复建档）
    """

    MAX_TURNS = MAX_TURNS

    def __init__(
        self,
        repo: CustomerServiceRepository,
        dify: DifyClient | None = None,
        crm_service: CrmService | None = None,
        customer_repo: CustomerRepository | None = None,
    ):
        self.repo = repo
        self.dify = dify or DifyClient()
        self.crm_service = crm_service
        self.customer_repo = customer_repo

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
        # 剥离 reasoning 模型的 <think> 思考块，防止污染标记解析与前端展示
        answer = THINK_RE.sub("", answer).strip()
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

        # 信息采集：[SLOTS]{json} 槽位剥离 → 留档 + 转线索/信息更新
        answer, slots = self._extract_slots(answer)
        # AI 信息提取兜底：Dify 未输出 [SLOTS] 时，从用户消息本地提取补充
        slots = self._local_extract_merge(slots, request.message)

        # 阶段3：高意向转线索——从用户消息/槽位提取手机号建档（携带画像字段，回填 session.customer_id）
        converted = False
        phone = self._extract_phone(request.message) or self._normalize_phone(slots.get("phone"))
        wechat = self._normalize_str(slots.get("wechat")) or self._extract_wechat(request.message)
        if phone and self.crm_service and not session.customer_id:
            try:
                lead_result = await self.crm_service.create_lead(
                    CrmLeadCreate(
                        phone=phone,
                        source="客服",
                        raw_input=request.message,
                        wechat=wechat,
                        **self._profile_kwargs(slots),
                    ),
                    None,
                )
                session.customer_id = lead_result["lead"]["customer_id"]
                await self.repo.update_session(session)
                converted = True
            except Exception:
                logger.exception("客服会话转线索失败")

        # 仅微信号无手机号 → 待补全线索 pending_lead（同号去重，反复沟通不重复建档）
        pending_created = False
        if wechat and not phone and not session.customer_id and self.customer_repo:
            try:
                existing = await self.repo.get_pending_lead_by_wechat(wechat)
                if existing is None:
                    await self.repo.create_pending_lead(
                        PendingLead(
                            wechat=wechat,
                            name=self._normalize_str(slots.get("name")),
                            raw_info=request.message,
                            source_session_id=session.id,
                        )
                    )
                    pending_created = True
            except Exception:
                logger.exception("客服会话待补全线索创建失败")

        # 信息更新：会话已关联客户时，新采集槽位补全画像（不重复建档）
        if not converted and session.customer_id and self.customer_repo:
            profile_updates = self._profile_kwargs(slots)
            if profile_updates:
                try:
                    customer = await self.customer_repo.get_by_id(session.customer_id)
                    if customer:
                        await self.customer_repo.update(customer, profile_updates)
                except Exception:
                    logger.exception("客服会话客户画像更新失败")

        # 阶段4：推荐落库（在建档之后执行，customer_id 关联更准确）
        for rec in recommendations or []:
            await self._save_recommendation(session, rec)

        if intent:
            await self.repo.add_intent_log(
                session.id,
                request.user_id,
                session.customer_id,
                intent,
                converted=converted or pending_created,
            )

        await self.repo.add_message(
            session.id, role="assistant", content=answer, intent=intent, slots=slots or None, card_data=card_data
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

    async def _save_recommendation(self, session, rec) -> None:
        """把单条推荐写入 cs_recommend_log（解析失败也保留 item_name 兜底，保证推荐可追溯）。"""
        if not isinstance(rec, dict):
            rec = {"name": str(rec)}
        course_id = self._to_int(rec.get("course_id"))
        event_id = self._to_int(rec.get("event_id"))
        rec_type = self._normalize_str(rec.get("type"))
        if course_id is None and event_id is None:
            rid = self._to_int(rec.get("id"))
            if rid is not None and rec_type == "event":
                event_id = rid
            elif rid is not None:
                course_id = rid
        if rec_type not in ("course", "event"):
            rec_type = "course" if course_id else "event" if event_id else "other"
        item_name = self._normalize_str(rec.get("name")) or self._normalize_str(rec.get("project"))
        try:
            await self.repo.add_recommend_log(
                session_id=session.id,
                customer_id=session.customer_id,
                course_id=course_id,
                event_id=event_id,
                recommendation_type=rec_type,
                item_name=item_name[:200] if item_name else None,
            )
        except Exception:
            logger.exception("客服推荐落库失败")

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

    @staticmethod
    def _extract_slots(answer: str) -> tuple[str, dict]:
        """剥离 answer 中的 [SLOTS]{json} 槽位标记，仅保留白名单字段（含 phone/wechat）。"""
        idx = answer.find(SLOTS_MARKER)
        if idx == -1:
            return answer, {}
        before = answer[:idx]
        json_part = answer[idx + len(SLOTS_MARKER) :].strip()
        slots: dict = {}
        try:
            parsed = json.loads(json_part)
            if isinstance(parsed, dict):
                for key in (*PROFILE_SLOT_FIELDS, "phone", "wechat"):
                    value = parsed.get(key)
                    if value not in (None, ""):
                        slots[key] = value
        except (json.JSONDecodeError, TypeError):
            pass
        if "age" in slots:
            try:
                slots["age"] = int(str(slots["age"]).strip().rstrip("岁"))
            except (TypeError, ValueError):
                slots.pop("age")
        return before.strip(), slots

    @classmethod
    def _local_extract_merge(cls, slots: dict, message: str) -> dict:
        """本地信息提取兜底：Dify 未输出 [SLOTS] 或缺字段时，从用户消息补充。

        规则：已有关键字段（phone/wechat/name/age/education/gender/study_intent）不覆盖，
        仅补充缺失项；提取值经 _normalize_slot_value 清洗。
        """
        if not message:
            return slots
        merged = dict(slots)
        for field, patterns in LOCAL_EXTRACT_PATTERNS.items():
            if field in merged and merged[field] not in (None, ""):
                continue
            for pattern in patterns:
                match = pattern.search(message)
                if match:
                    value = cls._normalize_slot_value(field, match.group(1))
                    if value is not None:
                        merged[field] = value
                    break
        return merged

    @staticmethod
    def _normalize_slot_value(field: str, raw: str) -> Any:
        """清洗本地提取的字段值，与 _extract_slots 的清洗规则对齐。"""
        text = raw.strip()
        if not text:
            return None
        if field == "age":
            try:
                return int(text)
            except ValueError:
                return None
        if field == "gender":
            return text if text in ("男", "女") else None
        return text

    @staticmethod
    def _extract_wechat(text: str) -> str | None:
        match = WECHAT_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _normalize_phone(value) -> str | None:
        if value is None:
            return None
        match = PHONE_RE.search(re.sub(r"[\s-]", "", str(value)))
        return match.group(0) if match else None

    @staticmethod
    def _normalize_str(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _to_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _profile_kwargs(slots: dict) -> dict:
        """从槽位中取出客户画像字段（过滤空值），供建档携带 / 老客户画像更新。"""
        kwargs = {}
        for field in PROFILE_SLOT_FIELDS:
            value = slots.get(field)
            if value not in (None, ""):
                kwargs[field] = value.strip() if isinstance(value, str) else value
        return kwargs


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
