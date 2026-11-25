"""M2 客服 Agent 服务（v6.10.2 从 ai_service.py 迁出，模块解耦）。

原文件 ai_service.py 为 M0 通用 AI 网关与 M2 客服双服务共存（v6.8.8 起），
存在跨模块耦合风险：M2 改动头部易波及 M3/M4 依赖的尾部通用 AIService。
本迁移后：客服 AiService 独立归位 M2 模块，ai_service.py 回归纯 M0 通用网关，
M3/M4 的 `from app.services.ai_service import AgentType, ai_service` 零改动。

逻辑与原实现逐行一致（4 出口 + [SLOTS] 槽位 + 本地提取兜底），仅文件位置变化。
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BusinessError
from app.models.customer import PendingLead
from app.models.user import User
from app.repositories.customer_repo import CustomerRepository
from app.repositories.customer_service_repo import CustomerServiceRepository
from app.repositories.event_repo import EventRepository
from app.repositories.user_repo import UserRepository
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.crm import CrmLeadCreate
from app.services.crm_service import CrmService
from app.services.dify_client import DifyClient
from app.services.event_service import EventService

# LangChain 引擎（CS_ENGINE=langchain 时使用，add_langchain 分支）
_cs_engine = None


def _get_langchain_engine():
    """懒加载 LangChain 引擎单例。"""
    global _cs_engine
    if _cs_engine is None:
        from app.services.cs_langchain.engine import CsLangChainEngine

        _cs_engine = CsLangChainEngine()
    return _cs_engine

logger = logging.getLogger(__name__)

# 客服单会话用户消息轮数上限，超过则归档旧会话并开启新会话（防止 Dify 上下文无限增长）
MAX_TURNS = 10
# 客服开场白（v6.10.3）：自研前端打开客服窗时经 GET /cs/greeting 拉取展示；
# 与 Dify 应用 opening_statement 同一文案，统一由本常量维护（Dify 开场白仅托管页生效，Service API 不返回）
CS_GREETING = "您好，我是粤教服务的智能客服小粤 😊 关于德国双元制、新加坡本硕、国际留学与研学，都可以问我～"
# 高意向转线索：从用户消息中提取大陆手机号
PHONE_RE = re.compile(r"1[3-9]\d{9}")
# 微信号提取：仅匹配显式关键词后跟 6-20 位字母开头的账号（防误伤普通英文单词）
WECHAT_RE = re.compile(r"(?:微信号|微信|vx|weixin|wechat)\s*[:：]?\s*([a-zA-Z][a-zA-Z0-9_-]{5,19})", re.IGNORECASE)
# Dify 输出约定标记（前向兼容，未输出时自动跳过）
INTENT_RE = re.compile(r"\[intent:([^\]]+)\]")
RECOMMEND_MARKER = "[RECOMMEND]"
SLOTS_MARKER = "[SLOTS]"
# P7/P8 对话内报名契约：[REGISTER]{"event_id": 2, "contact_name": "张三", "contact_phone": "13800138000"}
REGISTER_MARKER = "[REGISTER]"
# reasoning 模型思考块（<think>...</think>，含 <!--dify-deepseek-reasoning--> 注释），解析标记前先剥离
THINK_RE = re.compile(r"<think>.*?</think>\s*|<!--[^>]*reasoning[^>]*-->", re.DOTALL | re.IGNORECASE)

# P12 敏感信息后置过滤：银行账号（16-19 位连续数字）、身份证号（18 位含末位 X）
BANK_CARD_RE = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
SENSITIVE_REPLACEMENT = "具体缴费/身份信息请联系顾问获取"

# P5 FAQ 前置匹配：用户消息命中关键词即秒回 FAQ 原文（不进 Dify，保证与原文一致）
FAQ_KEYWORD_MIN_MATCH = 2  # 至少命中 N 个关键词才算命中

# 意图码归一（v6.10.6）：Dify 分支码 / seed 演示遗留码 → 后端契约 9 码（接口契约v1.md §客服，共用基准）
# 未识别码原样保留不吞数据；契约码原样透传；VM 分类器侧码表改造留作与 longtrying_test 线协调项
INTENT_ALIASES = {
    # VM Chatflow 分支码（7 分支 LLM prompt 自带码表）
    "business": "program_consult",
    "policy": "policy_qa",
    "event_signup": "event_query",
    # seed 演示数据遗留码（seed_data.py 旧词汇）
    "course_inquiry": "program_consult",
    "price_consult": "program_consult",
    "study_abroad_consult": "program_consult",
    "event_registration": "event_query",
    "general_chat": "chitchat",
}
CONTRACT_INTENTS = {
    "program_consult",
    "course_recommend",
    "policy_qa",
    "company_info",
    "event_query",
    "faq",
    "chitchat",
    "lead_capture",
    "transfer_human",
}

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
        event_service: EventService | None = None,
        user_repo: UserRepository | None = None,
    ):
        self.repo = repo
        self.dify = dify or DifyClient()
        self.crm_service = crm_service
        self.customer_repo = customer_repo
        self.event_service = event_service
        self.user_repo = user_repo

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not settings.DIFY_CUSTOMER_AGENT_KEY:
            raise BusinessError(code=50001, message="客服 Agent 未配置（DIFY_CUSTOMER_AGENT_KEY 为空）")
        session, faq_resp = await self._begin_turn(request)
        if faq_resp is not None:
            return faq_resp

        # LangChain 引擎分支（CS_ENGINE=langchain，add_langchain 分支）
        if settings.CS_ENGINE == "langchain":
            dify_resp = await self._langchain_answer(request, session)
        else:
            try:
                dify_resp = await self.dify.chat(
                    query=request.message,
                    user=str(request.user_id or "anonymous"),
                    conversation_id=session.dify_conversation_id,
                )
            except httpx.HTTPError as exc:
                # v6.11.30：Dify 超时/不可用不再直接抛 50001，走三级降级链（Dify→直连模型→本地话术），
                # 保证本轮一定有回复，避免前端弹"当前助手服务暂不可用"
                logger.warning("客服 Dify 调用失败（%s），走模型/本地降级", type(exc).__name__)
                fallback_answer = await self._fallback_answer(request.message, session)
                dify_resp = {"answer": fallback_answer, "conversation_id": session.dify_conversation_id or ""}
        return await self._finalize_turn(request, session, dify_resp)

    async def _langchain_answer(self, request: ChatRequest, session) -> dict:
        """LangChain 引擎分支：分类意图 → 组装伪标记 → 回答链。

        复用 _finalize_turn 既有 4 出口业务逻辑（意图归一/转线索/报名/推荐落库/敏感过滤/归档）。
        """
        engine = _get_langchain_engine()

        # 意图分类链（结构化输出，无正则标记依赖）
        classification = await engine.classify_intent(request.message)
        intent = classification.get("intent", "chitchat")
        slots = classification.get("slots", {})

        # 组装伪标记 + 回答正文（正文在前、标记在后，对齐 Dify 输出契约）
        from app.services.cs_langchain.schemas import format_as_markers

        markers = format_as_markers(intent, slots)
        answer = await engine.answer_blocking(request.message)
        full_answer = f"{answer}{markers}"
        return {"answer": full_answer, "conversation_id": session.dify_conversation_id or ""}

    async def _langchain_stream(self, request: ChatRequest, session) -> AsyncIterator[dict]:
        """LangChain 引擎流式分支：意图分类 → 标记扣留 → 回答链流式下发。

        流程：先跑意图分类链拿标记（不下发），再跑回答链流式下发正文，
        最后 _finalize_turn 解析标记落库。SSE 事件：meta/token/done。
        """
        engine = _get_langchain_engine()

        # 意图分类链（先跑完，拿标记不下发）
        classification = await engine.classify_intent(request.message)
        intent = classification.get("intent", "chitchat")
        slots = classification.get("slots", {})

        from app.services.cs_langchain.schemas import format_as_markers

        markers = format_as_markers(intent, slots)

        # 回答链流式下发正文（标记单独落库，不混入正文）
        buf = ""
        async for token in engine.answer_stream(request.message):
            buf += token
            yield {"event": "token", "delta": token}

        # _finalize_turn 需要带标记的完整 answer（正文在前、标记在后，对齐 Dify 输出契约）
        full_answer = f"{buf}{markers}"
        dify_resp = {"answer": full_answer, "conversation_id": session.dify_conversation_id or ""}
        resp = await self._finalize_turn(request, session, dify_resp)
        yield {"event": "done", "data": resp.model_dump()}

    async def _begin_turn(self, request: ChatRequest):
        """会话准备 + FAQ 秒回判定 + 多轮上限 + 用户消息落库。返回 (session, FAQ响应|None)。

        v6.11.37 抽出供 chat() 与 chat_stream() 共用，逻辑与原实现逐行一致。
        """
        session = await self._get_or_create_session(request)

        # P5 FAQ 前置匹配：命中即秒回 FAQ 原文（不经 Dify，保证与甲方原文一致且响应更快）
        faq_hit = await self._match_faq(request.message)
        if faq_hit:
            await self.repo.add_message(session.id, role="user", content=request.message)
            faq_card = {
                "faq": {
                    "faq_id": faq_hit.id,
                    "category": faq_hit.category,
                    "question": faq_hit.question,
                    "answer": faq_hit.answer,
                }
            }
            await self.repo.add_message(
                session.id, role="assistant", content=faq_hit.answer, intent="faq", card_data=faq_card
            )
            return session, ChatResponse(
                answer=faq_hit.answer, conversation_id=str(session.id), intent="faq", card_data=faq_card
            )

        # 阶段2：多轮上限——超过上限归档旧会话并开启新会话
        user_turns = await self.repo.count_messages(session.id, role="user")
        if user_turns >= self.MAX_TURNS:
            await self._archive_with_summary(session)
            session = await self.repo.create_session(request.user_id)

        await self.repo.add_message(session.id, role="user", content=request.message)
        return session, None

    async def _finalize_turn(self, request: ChatRequest, session, dify_resp: dict) -> ChatResponse:
        """Dify 应答（或降级应答）统一收尾：标记剥离、转线索、推荐落库、敏感过滤、消息留档。

        v6.11.37 抽出供 chat() 与 chat_stream() 共用，逻辑与原实现逐行一致。
        """
        answer = dify_resp.get("answer") or ""
        # 剥离 reasoning 模型的 <think> 思考块，防止污染标记解析与前端展示
        answer = THINK_RE.sub("", answer).strip()
        intent = dify_resp.get("intent")
        if dify_resp.get("conversation_id"):
            session.dify_conversation_id = dify_resp["conversation_id"]
            await self.repo.update_session(session)

        # 阶段1：意图标记剥离（优先 [intent:xxx]，其次 dify intent 字段）→ 归一到契约 9 码
        answer, intent_marker = self._extract_intent(answer)
        intent = intent_marker or intent
        intent = self.normalize_intent(intent)

        # 阶段4：推荐标记剥离 → card_data + recommendations
        answer, recommendations = self._extract_recommendations(answer)
        card_data = {"recommendations": recommendations} if recommendations else None

        # 信息采集：[SLOTS]{json} 槽位剥离 → 留档 + 转线索/信息更新
        answer, slots = self._extract_slots(answer)
        # AI 信息提取兜底：Dify 未输出 [SLOTS] 时，从用户消息本地提取补充
        slots = self._local_extract_merge(slots, request.message)

        # P7/P8 对话内报名：[REGISTER]{"event_id", "contact_name", "contact_phone"} → 调报名逻辑
        answer, register_card = await self._extract_and_register(answer, session, request.message)
        if register_card:
            card_data = register_card

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

        # 留资语义归位：转线索/待补全线索成功即 lead_capture（契约码，v6.10.6）
        if converted or pending_created:
            intent = "lead_capture"

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

        # P12 敏感信息后置过滤：银行账号/身份证号替换为统一话术（兜底 P0 红线，防知识库原文外泄）
        answer = self._filter_sensitive(answer)

        await self.repo.add_message(
            session.id, role="assistant", content=answer, intent=intent, slots=slots or None, card_data=card_data
        )
        return ChatResponse(
            answer=answer,
            conversation_id=str(session.id),
            intent=intent,
            recommendations=recommendations,
            card_data=card_data,
        )

    # ── v6.11.37：流式对话（SSE 增量下发，感知延迟=首字时间） ──────────
    _STREAM_OPENERS = ("[intent:", "[RECOMMEND", "[SLOTS", "[REGISTER")

    @classmethod
    def _stream_advance(cls, buf: str, cursor: int) -> tuple[str, int]:
        """把 [cursor, len(buf)) 中「可公开下发」的部分返回并推进游标。

        - `<think>...` 思考块整体跳过（未闭合时等待，不下发）；
        - 标记区（[intent:] 等，契约规定位于正文之后）起点起永久扣留，
          由 _finish_turn 的既有剥离管线统一解析落库，不污染前端展示。
        """
        out: list[str] = []
        i, n = cursor, len(buf)
        while i < n:
            if buf.startswith("<think>", i):
                j = buf.find("`", i)
                if j < 0:
                    return "".join(out), i
                i = j + 2
                continue
            if buf.startswith(cls._STREAM_OPENERS, i):
                return "".join(out), i
            out.append(buf[i])
            i += 1
        return "".join(out), i

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[dict]:
        """流式客服对话：逐段下发正文增量，结束下发 done（含标记解析后的结构化数据）。

        事件：{"event":"meta","conversation_id"} / {"event":"token","delta"} / {"event":"done","data"}。
        Dify 流失败即走降级链（流未开始→模型/本地话术一次性下发；流中断→按已收内容收尾），
        保证前端必收 done 事件。
        """
        if not settings.DIFY_CUSTOMER_AGENT_KEY:
            raise BusinessError(code=50001, message="客服 Agent 未配置（DIFY_CUSTOMER_AGENT_KEY 为空）")
        session, faq_resp = await self._begin_turn(request)
        if faq_resp is not None:
            yield {"event": "done", "data": faq_resp.model_dump()}
            return
        yield {"event": "meta", "conversation_id": str(session.id)}

        # LangChain 引擎分支（CS_ENGINE=langchain，add_langchain 分支）
        if settings.CS_ENGINE == "langchain":
            async for ev in self._langchain_stream(request, session):
                yield ev
            return

        buf = ""
        cursor = 0
        dify_conv_id: str | None = None
        stream_error: Exception | None = None
        try:
            async for chunk in self.dify.chat_stream(
                query=request.message,
                user=str(request.user_id or "anonymous"),
                conversation_id=session.dify_conversation_id,
            ):
                delta = chunk.get("delta")
                if delta:
                    buf += delta
                    emit, cursor = self._stream_advance(buf, cursor)
                    if emit:
                        yield {"event": "token", "delta": emit}
                elif chunk.get("conversation_id"):
                    dify_conv_id = chunk["conversation_id"]
        except httpx.HTTPError as exc:
            stream_error = exc

        conv_id = dify_conv_id or session.dify_conversation_id or ""
        if stream_error is not None and not buf:
            logger.warning("客服 Dify 流式调用失败（%s），走模型/本地降级", type(stream_error).__name__)
            fallback_answer = await self._fallback_answer(request.message, session)
            dify_resp = {"answer": fallback_answer, "conversation_id": conv_id}
        else:
            if stream_error is not None:
                logger.warning("客服 Dify 流中断（%s），按已收内容收尾", type(stream_error).__name__)
            dify_resp = {"answer": buf, "conversation_id": conv_id}

        resp = await self._finalize_turn(request, session, dify_resp)
        yield {"event": "done", "data": resp.model_dump()}

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
    def normalize_intent(intent: str | None) -> str | None:
        """意图码归一：Dify 分支码 / seed 遗留码 → 契约 9 码；契约码透传；未识别码原样保留。"""
        if not intent:
            return intent
        key = intent.strip()
        if key in CONTRACT_INTENTS:
            return key
        mapped = INTENT_ALIASES.get(key)
        if mapped:
            return mapped
        logger.debug("未识别的意图码，原样保留：%s", key)
        return key

    @staticmethod
    def _extract_intent(answer: str) -> tuple[str, str | None]:
        # 多轮时模型会模仿 Dify 历史中的原始标记而输出多个 [intent:]，取首个为意图、全部剥离（v6.11.22）
        matches = list(INTENT_RE.finditer(answer))
        if not matches:
            return answer, None
        cleaned = INTENT_RE.sub("", answer).strip()
        return cleaned, matches[0].group(1).strip()

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

    # ── v6.11.30：Dify 失败降级链（直连模型 → 本地话术） ──────────────
    async def _fallback_answer(self, message: str, session) -> str:
        """Dify 超时/不可用时的兜底回复：先试直连模型（OpenAI-compatible），失败用本地话术。

        模型调用限 35s（Dify 25s + 模型 35s = 60s < 前端 70s 超时），保证前端一定收到回复。
        """
        try:
            from app.services.model_ai_service import model_ai_service

            result = await asyncio.wait_for(model_ai_service.chat(message, str(session.id), None), timeout=35)
            reply = (result.get("reply") or "").strip()
            if reply:
                return reply
        except Exception as model_exc:
            logger.warning("客服模型降级失败，改本地话术: %s", model_exc)
        return (
            "抱歉，智能助手本轮响应较慢，未能及时给出回答。您可以稍后重新发送，"
            "或留下联系方式与具体需求，我们会安排顾问跟进。"
        )

    # ── P5 FAQ 前置匹配 ──────────────────────────────────────────
    async def _match_faq(self, message: str):
        """用户消息与 FAQ 做关键词 + 字符级相似度匹配，命中即返回 FAQ 原文。"""
        if not message or len(message.strip()) < 2:
            return None
        faqs, _ = await self.repo.list_faqs(page=1, page_size=200)
        msg = self._strip_punct(message.strip())
        msg_chars = set(msg)
        if not msg_chars:
            return None
        best, best_score = None, 0
        for faq in faqs:
            keywords = [k.strip() for k in (faq.keywords or "").split(",") if k.strip()]
            score = sum(1 for k in keywords if k and k in message)
            # question 去标点后与用户消息做字符级 Jaccard 相似度
            q_chars = set(self._strip_punct(faq.question or ""))
            if q_chars:
                jaccard = len(msg_chars & q_chars) / len(msg_chars | q_chars)
                if jaccard >= 0.5:
                    score += 2 + int(jaccard * 3)
            if score > best_score:
                best_score, best = score, faq
        if best and best_score >= FAQ_KEYWORD_MIN_MATCH:
            return best
        return None

    @staticmethod
    def _strip_punct(text: str) -> str:
        return re.sub(r"[？?。！!，,；;：:、\s「」『』\"'()（）]", "", text)

    # ── P7/P8 对话内报名 ────────────────────────────────────────
    @staticmethod
    def _extract_register(answer: str) -> tuple[str, dict | None]:
        idx = answer.find(REGISTER_MARKER)
        if idx == -1:
            return answer, None
        before = answer[:idx]
        json_part = answer[idx + len(REGISTER_MARKER) :].strip()
        try:
            parsed = json.loads(json_part)
            if isinstance(parsed, dict):
                return before.strip(), parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return before.strip(), None

    async def _extract_and_register(self, answer: str, session, user_message: str) -> tuple[str, dict | None]:
        answer, register_data = self._extract_register(answer)
        if not register_data:
            return answer, None
        event_id = self._to_int(register_data.get("event_id"))
        contact_name = self._normalize_str(register_data.get("contact_name"))
        contact_phone = self._normalize_phone(register_data.get("contact_phone")) or self._extract_phone(user_message)
        if not event_id or not contact_phone:
            return answer, {"register": {"status": "incomplete", "message": "请补充活动编号和联系电话"}}

        # event_registration.user_id NOT NULL：匿名访客无法直接报名，引导先登录
        if not session.user_id:
            return answer, {"register": {"status": "need_login", "message": "报名需先登录，请先注册/登录后再试"}}

        if not self.event_service or not self.user_repo:
            return answer, {"register": {"status": "error", "message": "报名服务暂不可用"}}

        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            return answer, {"register": {"status": "error", "message": "用户信息异常，请重新登录"}}

        try:
            result = await self.event_service.register(event_id, user)
            return answer, {
                "register": {
                    "status": "success",
                    "event_id": event_id,
                    "contact_name": contact_name or user.real_name,
                    "contact_phone": contact_phone,
                    "registration_id": result.get("id"),
                    "message": f"报名成功！已为「{contact_name or user.real_name}」登记，联系电话 {contact_phone}",
                }
            }
        except BusinessError as e:
            return answer, {"register": {"status": "failed", "message": e.message or "报名失败"}}
        except Exception:
            logger.exception("客服对话内报名失败")
            return answer, {"register": {"status": "error", "message": "报名失败，请稍后重试"}}

    # ── P12 敏感信息后置过滤 ────────────────────────────────────
    @staticmethod
    def _filter_sensitive(text: str) -> str:
        if not text:
            return text
        text = BANK_CARD_RE.sub(SENSITIVE_REPLACEMENT, text)
        text = ID_CARD_RE.sub(SENSITIVE_REPLACEMENT, text)
        return text

    # ── P11 会话摘要与标签 ──────────────────────────────────────
    async def _archive_with_summary(self, session) -> None:
        """归档会话：生成摘要 + 标签后落库 intent_summary / tags_json，再标 archived。"""
        try:
            messages = await self.repo.list_messages(session.id)
            if messages:
                transcript = "\n".join(f"{m.role}: {m.content[:200]}" for m in messages[-20:])
                summary_prompt = (
                    "请用不超过80字概括以下客服对话的用户核心诉求与最终结论，"
                    "并输出3个以内的标签。格式：{\"summary\":\"...\",\"tags\":[\"...\"]}\n\n"
                    f"对话：\n{transcript}"
                )
                dify_resp = await self.dify.chat(
                    query=summary_prompt,
                    user=f"summary-{session.id}",
                    conversation_id=None,
                )
                raw = THINK_RE.sub("", dify_resp.get("answer") or "").strip()
                summary, tags = self._parse_summary(raw)
                session.intent_summary = summary
                session.tags_json = tags
        except Exception:
            logger.exception("客服会话摘要生成失败")
        session.status = "archived"
        await self.repo.update_session(session)

    @staticmethod
    def _parse_summary(raw: str) -> tuple[str | None, list | None]:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                summary = str(parsed.get("summary") or "").strip()[:500] or None
                tags = parsed.get("tags")
                if isinstance(tags, list):
                    tags = [str(t) for t in tags[:10]]
                return summary, tags
        except (json.JSONDecodeError, TypeError):
            pass
        # 兜底：非 JSON 时取首行作为摘要
        first_line = raw.splitlines()[0].strip()[:500] if raw else None
        return first_line, None
