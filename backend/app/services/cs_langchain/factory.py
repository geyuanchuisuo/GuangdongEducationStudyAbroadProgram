"""模型工厂：云端 DeepSeek（对齐 DIFY_MODEL_*）优先，本地 Ollama 降级。

对应学习笔记 utils/model_utils.py 的 get_model() 思路。
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def get_model():
    """获取聊天模型实例。

    1. DIFY_MODEL_* 已配置 → ChatOpenAI（DeepSeek/通义等 OpenAI 兼容网关）
    2. 未配置 → ChatOllama（本地，需 ollama serve + 已拉取模型）
    """
    if settings.DIFY_MODEL_API_KEY and settings.DIFY_MODEL_BASE_URL:
        from langchain_openai import ChatOpenAI

        logger.info("客服 LangChain 模型：云端 ChatOpenAI（%s / %s）",
                    settings.DIFY_MODEL_BASE_URL, settings.DIFY_MODEL_NAME)
        return ChatOpenAI(
            model=settings.DIFY_MODEL_NAME,
            api_key=settings.DIFY_MODEL_API_KEY,
            base_url=settings.DIFY_MODEL_BASE_URL,
            temperature=0.3,
            timeout=35,
        )

    # 本地降级
    from langchain_ollama import ChatOllama

    host = settings.OLLAMA_BASE_URL
    logger.info("客服 LangChain 模型：本地 ChatOllama（%s）", host)
    return ChatOllama(
        model="qwen2.5:7b",
        base_url=host,
        temperature=0.3,
    )
