"""OpenAI-compatible model gateway for report analysis."""
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ModelAIService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=45)
        return self._client

    async def analyze(self, report_type: str, metrics: dict) -> dict | None:
        if not settings.DIFY_MODEL_API_KEY:
            return None
        prompt = (
            "你是粤教留学项目的智能报告分析助手。只能基于给定指标归纳摘要、趋势、分析和建议，"
            "禁止自行计算数字或编造数据。输出 JSON，字段必须为 summary、trend、analysis、suggestions。" + chr(10) +
            "报告类型：" + report_type + chr(10) + "指标数据：" + json.dumps(metrics, ensure_ascii=False)
        )
        payload = {
            "model": settings.DIFY_MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只输出 JSON，不要输出 Markdown。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        try:
            client = await self._get_client()
            response = await client.post(
                settings.DIFY_MODEL_BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + settings.DIFY_MODEL_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            text = content.strip()
            if text.startswith(chr(96) * 3):
                text = text.strip(chr(96))
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            return json.loads(text)
        except Exception as exc:
            logger.warning("Model analysis failed: %s", exc)
            return None

    async def chat(self, message: str, session_id: str, context: dict | None = None) -> dict:
        if not settings.DIFY_MODEL_API_KEY:
            raise ValueError("DIFY_MODEL_API_KEY is not configured")
        system = "你是粤教留学项目的智能助手。根据用户身份和能力范围回答，不能编造业务数据。"
        content = message
        if context:
            content = "用户上下文：" + json.dumps(context, ensure_ascii=False) + chr(10) + "用户消息：" + message
        payload = {
            "model": settings.DIFY_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
        }
        client = await self._get_client()
        response = await client.post(
            settings.DIFY_MODEL_BASE_URL.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + settings.DIFY_MODEL_API_KEY, "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        message_data = response.json()["choices"][0].get("message", {})
        reply = message_data.get("content") or message_data.get("reasoning_content") or ""
        return {"reply": reply.strip(), "session_id": session_id or "model"}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


model_ai_service = ModelAIService()
