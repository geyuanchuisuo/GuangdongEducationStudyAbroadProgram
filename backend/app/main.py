from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import ai, auth, courses, crm, events, users
from app.api.v1 import assessment as assessment_save_api
from app.assessment.router import router as assessment_engine_router
from app.config import settings
from app.core.exceptions import BusinessError
from app.core.middleware import RequestLogMiddleware
from app.core.response import error_response
from app.database import engine
from app.models import Base
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动: %s", settings.PROJECT_NAME)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表初始化完成（共 %d 张表）", len(Base.metadata.tables))
    yield
    await engine.dispose()
    logger.info("应用关闭")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLogMiddleware)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    logger.warning(
        "业务异常 [%s] %s: code=%s message=%s",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    return JSONResponse(status_code=200, content=error_response(code=exc.code, message=exc.message))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "未处理异常 [%s] %s: %s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(status_code=500, content=error_response(code=50001, message="服务器内部错误"))


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(crm.router, prefix=settings.API_V1_PREFIX)
app.include_router(courses.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai.router, prefix=settings.API_V1_PREFIX)
app.include_router(assessment_engine_router, prefix=settings.API_V1_PREFIX)
app.include_router(assessment_save_api.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
