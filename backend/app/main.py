from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    approvals,
    auth,
    customers,
    employees,
    files,
    notifications,
    operation_logs,
    reports,
    students,
    users,
)
from app.config import settings
from app.core.exceptions import BusinessError
from app.core.middleware import RequestLogMiddleware
from app.core.response import error_response
from app.database import engine
from app.models import Base
from app.services.employee_event_handlers import (
    handle_customer_registered,
    handle_psych_alert_created,
)
from app.services.event_bus import event_bus
from app.services.event_contracts import EventType
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动: %s", settings.PROJECT_NAME)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表初始化完成（共 %d 张表）", len(Base.metadata.tables))

    # M3 员工模块：订阅事件 → 生成员工待办
    event_bus.subscribe(EventType.CUSTOMER_REGISTERED.value, handle_customer_registered)
    event_bus.subscribe(EventType.PSYCH_ALERT_CREATED.value, handle_psych_alert_created)
    logger.info("M3 事件订阅完成：customer.registered / psych_alert.created")

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
    trace_id = getattr(request.state, "request_id", "")
    logger.warning(
        "业务异常 [%s] [%s] %s: code=%s message=%s",
        trace_id,
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    # 异常处理器必须返回 Response 对象，直接返回 dict 会导致 Starlette 报
    # "'dict' object is not callable" 并退化为 500；统一按契约返回 HTTP 200 + 业务码
    return JSONResponse(content=error_response(code=exc.code, message=exc.message, trace_id=trace_id))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "request_id", "")
    logger.exception(
        "未处理异常 [%s] [%s] %s: %s",
        trace_id,
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(content=error_response(code=50001, message="服务器内部错误", trace_id=trace_id))


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(customers.router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(files.router, prefix=settings.API_V1_PREFIX)
app.include_router(employees.router, prefix=settings.API_V1_PREFIX)
app.include_router(operation_logs.router, prefix=settings.API_V1_PREFIX)
app.include_router(students.router, prefix=settings.API_V1_PREFIX)          # M4 学生模块（学生端）
app.include_router(students.employee_router, prefix=settings.API_V1_PREFIX)  # M4 进度追踪员工端更新
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)           # M5 报告模块


@app.get("/health")
async def health_check():
    return {"status": "ok"}
