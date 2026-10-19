import json

import httpx

from app.config import settings


class DifyClient:
    """Dify 智能客服 Agent 调用客户端。

    说明：一期按 Dify 原生 /chat-messages(blocking) 协议实现（对齐 docs/项目需求文档.md §12.3）。
    注意：config.DIFY_API_PROTOCOL="openai" 与文档样例存在矛盾，一期暂按原生协议实现，待定。
    """

    def __init__(self, base_url: str | None = None, agent_key: str | None = None):
        self.base_url = (base_url or settings.DIFY_BASE_URL).rstrip("/")
        self.agent_key = agent_key or settings.DIFY_CUSTOMER_AGENT_KEY

    async def chat(self, query: str, user: str, conversation_id: str | None = None) -> dict:
        url = f"{self.base_url}/v1/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.agent_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        # v6.11.30：超时 60s→25s——Chatflow 多 LLM 节点串行耗时波动大（19~60s+），
        # 25s 未返回即让调用方走模型/本地降级，避免前端 30s 超时弹"暂不可用"后端还挂 60s
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def chat_stream(self, query: str, user: str, conversation_id: str | None = None):
        """流式对话（response_mode=streaming）：逐段产出 {"delta": str}，结束产出 {"conversation_id": str}。

        v6.11.37：供 cs_agent_service.chat_stream 做 SSE 增量下发（感知延迟=首字时间）。
        读超时 25s 表示「相邻数据块间隔」——生成中持续来块不会误杀；断流/超时抛错由调用方降级兜底。
        """
        url = f"{self.base_url}/v1/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.agent_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "streaming",
            "user": user,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        conv_id = conversation_id or ""
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, read=25.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    event = data.get("event")
                    if event == "error":
                        raise httpx.HTTPError(f"Dify stream error: {data}")
                    if data.get("conversation_id"):
                        conv_id = data["conversation_id"]
                    answer = data.get("answer")
                    if answer:
                        yield {"delta": answer}
        yield {"conversation_id": conv_id}
