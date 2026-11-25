"""客服 LangChain 模块：结构化输出 schema 与伪标记组装。

意图分类链用 JsonOutputParser + IntentOutput Pydantic 一次解析出
intent + slots，再组装成与 Dify 标记协议一致的伪标记，复用
cs_agent_service 既有剥离管线（_extract_intent/_extract_slots/_extract_recommendations）。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# 契约 9 码（与 cs_agent_service.CONTRACT_INTENTS 对齐）
CONTRACT_INTENTS = (
    "program_consult",
    "course_recommend",
    "policy_qa",
    "company_info",
    "event_query",
    "faq",
    "chitchat",
    "lead_capture",
    "transfer_human",
)

# 人设模板对槽位字段的要求（与 cs_agent_service.PROFILE_SLOT_FIELDS + phone/wechat 对齐）
SLOT_FIELDS = (
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
    "phone",
    "wechat",
)


class IntentOutput(BaseModel):
    """意图分类链结构化输出：仅提取用户消息中已明确出现的槽位，不得编造。"""

    intent: str = Field(
        description=f"本轮意图，必须是以下之一：{'、'.join(CONTRACT_INTENTS)}；无法归类时用 chitchat",
    )
    slots: dict[str, Any] = Field(
        default_factory=dict,
        description="本轮对话中客户明确提到的画像信息，未提及的字段不要出现在对象中",
    )


def format_as_markers(intent: str, slots: dict[str, Any]) -> str:
    """把分类结果组装成 Dify 标记协议格式，供 cs_agent_service 既有剥离管线消费。

    未识别意图回退 chitchat（与 prompt 约束一致，保底不吞意图）；
    空 slots 不输出 [SLOTS]。
    """
    intent_code = intent if intent in CONTRACT_INTENTS else "chitchat"
    parts: list[str] = [f"[intent:{intent_code}]"]
    if slots:
        parts.append(f"[SLOTS]{json.dumps(slots, ensure_ascii=False)}")
    return "".join(parts)


intent_parser = JsonOutputParser(pydantic_object=IntentOutput)
