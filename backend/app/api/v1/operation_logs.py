from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.employee_repo import (
    DailyReportRepository,
    OrgRepository,
    ScoreRepository,
    TodoRepository,
)
from app.schemas.employee import OperationLogItem
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/operation-logs", tags=["操作日志"])


def _get_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    # 与 employees.py._get_service 保持一致：EmployeeService 需要完整仓储依赖
    return EmployeeService(
        db=db,
        report_repo=DailyReportRepository(db),
        todo_repo=TodoRepository(db),
        org_repo=OrgRepository(db),
        score_repo=ScoreRepository(db),
    )


@router.get("", summary="操作日志查询（MANAGER，按操作类型/操作人/时间筛选）")
async def list_operation_logs(
    action_type: str | None = Query(None, description="操作类型，如 customer_status_change/customer_reassign/phone_reveal"),
    operator_id: int | None = Query(None, description="操作人用户ID"),
    start: date | None = Query(None, description="起始日期（含）"),
    end: date | None = Query(None, description="结束日期（含当天）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    logs, total = await service.list_operation_logs(
        action_type, operator_id, start, end, page, page_size
    )
    return success_response(
        data={
            "items": [OperationLogItem.model_validate(log) for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
