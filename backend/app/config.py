from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "粤教留学项目管理平台"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:59000/GuangdongEducationStudyAbroadProgram"

    REDIS_URL: str = "redis://localhost:6379"

    SECRET_KEY: str = "change-this-to-a-secure-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DIFY_BASE_URL: str = "http://localhost:8081"
    DIFY_VERSION: str = "1.16.0-rc1"
    DIFY_API_PROTOCOL: str = "openai"
    DIFY_STUDENT_AGENT_KEY: str = ""
    DIFY_EMPLOYEE_AGENT_KEY: str = ""
    DIFY_CUSTOMER_AGENT_KEY: str = ""
    DIFY_REPORT_AGENT_KEY: str = ""
    # 直连模型降级（Dify Agent 不可用时用，留空则跳过直连降级走本地话术）
    # 模型为 OpenAI-API-compatible 通用配置：key/url/模型名均由客户自定义，默认全空，不绑定任何特定模型
    DIFY_MODEL_API_KEY: str = ""
    DIFY_MODEL_BASE_URL: str = ""
    DIFY_MODEL_NAME: str = ""

    # Dify Agent 单次请求超时（秒）。报告生成为同步阻塞调用，最坏耗时 ≈ 超时 × 尝试次数（3 次），
    # 网络质量差或需快速失败时按需调低；默认值与原硬编码 60s 一致
    DIFY_AI_TIMEOUT: float = 60.0

    # M5 智能报告数据来源开关（M5-02.3）：mock=模拟数据（默认）；production=真实业务表取数
    REPORT_DATA_SOURCE: str = "mock"

    # 文件存储后端：local=本地磁盘（默认，一期单机 Docker 零外部依赖）/ s3=MinIO 等 S3 兼容存储（二期生产可选）
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "./storage_data"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "password"
    MINIO_BUCKET: str = "education"

    # 客服引擎开关（add_langchain 分支）：dify=Dify Chatflow（默认，可回滚）/ langchain=LangChain 本地链路
    CS_ENGINE: str = "dify"

    # ── 知识库混合检索（独立 /knowledge 接口，2026-10-24 新增；仅追加键，未改任何已有配置） ──
    # Milvus 与 Ollama 均部署在宿主机：本地开发直连 localhost；
    # backend 在 Docker 容器内运行时，.env 改为 http://host.docker.internal:19530 / :11434
    # 注意用 127.0.0.1 而非 localhost：本机 localhost 可能解析为 IPv6(::1)，
    # 而 Milvus/Ollama 只监听 IPv4，IPv6 连接会被中途重置（LOG-117 根因）
    MILVUS_URI: str = "http://127.0.0.1:19530"
    MILVUS_COLLECTION: str = "yuejiao_knowledge"
    # v6.14.0：问答对独立集合（仅对 question 向量化，问题-问题匹配）
    MILVUS_FAQ_COLLECTION: str = "yuejiao_faq"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    EMBED_MODEL: str = "bge-m3"
    EMBED_DIM: int = 1024
    KNOWLEDGE_DOCS_DIR: str = "../docs/教育服务"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
