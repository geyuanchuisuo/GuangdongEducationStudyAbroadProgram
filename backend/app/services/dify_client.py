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
