"""RAGAS 裁判模型与嵌入模型装配（复用粤教项目网关配置，零改业务代码）。

- 裁判 LLM：项目 DIFY_MODEL_* 网关（当前 deepseek-flash），OpenAI 兼容，
  经 LangchainLLMWrapper 包装成 ragas 可用的判定模型。
- 嵌入模型：本机 Ollama bge-m3（与生产检索同源），经 LangchainEmbeddingsWrapper 包装。

注意：本模块必须在 CWD=backend/ 下导入（app.config 的 env_file 是相对路径 ".env"），
由 run_eval.py 负责 chdir + sys.path 注入后再调用这里的工厂函数。
"""

from __future__ import annotations


def build_judge_llm():
    """构造 ragas 裁判 LLM（deepseek-flash，低温求稳）。"""
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    from app.config import settings

    if not (settings.DIFY_MODEL_API_KEY and settings.DIFY_MODEL_BASE_URL and settings.DIFY_MODEL_NAME):
        raise RuntimeError(
            "裁判模型未配置：backend/.env 的 DIFY_MODEL_API_KEY / DIFY_MODEL_BASE_URL / "
            "DIFY_MODEL_NAME 存在空值，无法进行 ragas 评估。"
        )

    chat = ChatOpenAI(
        model=settings.DIFY_MODEL_NAME,
        base_url=settings.DIFY_MODEL_BASE_URL.rstrip("/"),
        api_key=settings.DIFY_MODEL_API_KEY,
        temperature=0.0,
        timeout=120,
        max_retries=2,
    )
    return LangchainLLMWrapper(chat), settings.DIFY_MODEL_NAME


def build_embeddings():
    """构造 ragas 嵌入模型（本机 Ollama bge-m3，与生产检索同源）。"""
    from langchain_ollama import OllamaEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    from app.config import settings

    emb = OllamaEmbeddings(
        model=settings.EMBED_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )
    return LangchainEmbeddingsWrapper(emb), settings.EMBED_MODEL


def build_metrics():
    """RAGAS 四指标实例（检索两项 + 生成两项）。"""
    from ragas.metrics import (
        AnswerRelevancy,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )

    return [
        LLMContextPrecisionWithReference(),  # 上下文精确率（参照 ground_truth）
        LLMContextRecall(),                  # 上下文召回率（参照 ground_truth）
        Faithfulness(),                      # 忠实度（回答是否只依据检索上下文）
        # strictness=1：AnswerRelevancy 默认 n=3 次反向提问，但项目网关只支持 n=1，
        # 会触发 400「Invalid n value」；降到 1 次干净通过（分数仍有效）。
        AnswerRelevancy(strictness=1),       # 答案相关性（是否切题完整）
    ]
