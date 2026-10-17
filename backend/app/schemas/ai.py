from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    conversation_id: str | None = Field(None, description="会话ID（前端维护，可空）")
    user_id: int | None = Field(None, description="已登录用户ID（访客为空）")


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    intent: str | None = None
    recommendations: list[dict] | None = None
