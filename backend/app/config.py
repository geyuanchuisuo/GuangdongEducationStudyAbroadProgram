from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "粤教留学项目管理平台"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:59000/GuangdongEducationStudyAbroadProgram"

    REDIS_URL: str = "redis://localhost:6379"

    SECRET_KEY: str = "change-this-to-a-secure-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DIFY_BASE_URL: str = "http://localhost"
    DIFY_VERSION: str = "1.16.0-rc1"
    DIFY_API_PROTOCOL: str = "openai"
    DIFY_STUDENT_AGENT_KEY: str = ""
    DIFY_EMPLOYEE_AGENT_KEY: str = ""
    DIFY_CUSTOMER_AGENT_KEY: str = ""
    # v6.11.3：M5 报告专用 Agent（未配置时报告 AI 显式标不可用，不回落其他 Agent）
    DIFY_REPORT_AGENT_KEY: str = ""
    DIFY_MODEL_API_KEY: str = ""
    DIFY_MODEL_BASE_URL: str = "https://apihub.agnes-ai.com/v1"
    DIFY_MODEL_NAME: str = "agnes-2.5-flash"

    # M5 智能报告数据来源开关（M5-02.3）：mock=模拟数据（默认）；production=真实业务表取数
    REPORT_DATA_SOURCE: str = "mock"

    # 文件存储后端：local=本地磁盘（默认，一期单机 Docker 零外部依赖）/ s3=MinIO 等 S3 兼容存储（二期生产可选）
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "./storage_data"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "password"
    MINIO_BUCKET: str = "education"

    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
