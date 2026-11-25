"""客服 LangChain 模块（add_langchain 分支）。

用 LangChain 组件（Model/Prompt/Output Parser/Memory）替代 Dify HTTP 调用：
- schemas：意图分类结构化输出（IntentOutput Pydantic）
- prompts：分类 PromptTemplate + 人设模板
- factory：ChatOpenAI（DeepSeek 云端，对齐 DIFY_MODEL_*）/ ChatOllama（本地降级）
- engine：CsLangChainEngine——分类链 + 回答链 + FAQ 向量秒回
- rag_retriever：KnowledgeService 双集合检索（yuejiao_knowledge + yuejiao_faq）适配

设计原则（最小改动）：LangChain 链路输出「[intent:xxx][SLOTS]{json}」伪标记，
复用 cs_agent_service 既有 4 出口业务逻辑（意图归一/转线索/报名/推荐落库/敏感过滤/归档）。
"""
