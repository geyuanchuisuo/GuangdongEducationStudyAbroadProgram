from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.employee_repo import (
    DailyReportRepository,
    OrgRepository,
    ScoreRepository,
    TodoRepository,
)
from app.schemas.employee import (
    ConvertApplyCreate,
    ConvertApplyOut,
    DailyReportCreate,
    DailyReportOut,
    DailyReportSummaryItem,
    OrgNode,
    ScoreCreate,
    ScoreOut,
    TodoCreate,
    TodoOut,
    TodoUpdate,
)
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employee", tags=["员工模块"])


def _get_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    return EmployeeService(
        db=db,
        report_repo=DailyReportRepository(db),
        todo_repo=TodoRepository(db),
        org_repo=OrgRepository(db),
        score_repo=ScoreRepository(db),
    )


# ── 日报 ──────────────────────────────────────────────
@router.post("/reports", summary="提交日报")
async def submit_report(
    data: DailyReportCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    report = await service.submit_report(current_user.id, data.report_date, data.content)
    return success_response(data=DailyReportOut.model_validate(report), message="日报已提交")


@router.get("/reports", summary="日报列表（员工看自己/管理层看全部；M5 对外）")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: EmployeeService = Depends(_get_service),
):
    if current_user.user_type == "EMPLOYEE":
        items, total = await service.list_my_reports(current_user.id, page, page_size)
    else:
        items, total = await service.list_all_reports(page, page_size)
    return success_response(
        data={
            "items": [DailyReportOut.model_validate(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/reports/summary", summary="日报汇总（M5 对外）")
async def reports_summary(
    start: date | None = Query(None),
    end: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    service: EmployeeService = Depends(_get_service),
):
    rows = await service.reports_summary(start, end)
    items = [DailyReportSummaryItem(report_date=d, submitted=c) for d, c in rows]
    return success_response(data={"items": items})


# ── 待办 ──────────────────────────────────────────────
@router.post("/todos", summary="创建待办")
async def create_todo(
    data: TodoCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    todo = await service.create_todo(current_user.id, data.model_dump(exclude_unset=True))
    return success_response(data=TodoOut.model_validate(todo), message="创建成功")


@router.get("/todos", summary="待办列表")
async def list_todos(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items, total = await service.list_my_todos(current_user.id, status, page, page_size)
    return success_response(
        data={
            "items": [TodoOut.model_validate(t) for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.put("/todos/{todo_id}", summary="更新待办")
async def update_todo(
    todo_id: int,
    data: TodoUpdate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    todo = await service.update_todo(todo_id, current_user.id, data.model_dump(exclude_unset=True))
    return success_response(data=TodoOut.model_validate(todo), message="更新成功")


# ── 组织架构 ──────────────────────────────────────────
@router.get("/org", summary="组织架构树")
async def get_org(
    current_user: User = Depends(get_current_user),
    service: EmployeeService = Depends(_get_service),
):
    rows = await service.get_org_tree()
    nodes = {
        r.id: OrgNode(
            id=r.id, name=r.name, parent_id=r.parent_id, org_type=r.org_type,
            leader_id=r.leader_id, sort_order=r.sort_order, status=r.status, children=[]
        ) for r in rows
    }
    roots: list[OrgNode] = []
    for node in nodes.values():
        if node.parent_id and node.parent_id in nodes:
            nodes[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return success_response(data={"items": roots})


# ── 成绩 ──────────────────────────────────────────────
@router.post("/scores", summary="录入成绩")
async def record_score(
    data: ScoreCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    score = await service.record_score(data.model_dump(exclude_unset=True))
    return success_response(data=ScoreOut.model_validate(score), message="成绩已录入")


@router.get("/scores", summary="成绩列表（员工/管理层查询）")
async def list_scores(
    student_id: int | None = Query(None),
    semester: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items, total = await service.list_scores(student_id, semester, page, page_size)
    return success_response(
        data={
            "items": [ScoreOut.model_validate(s) for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


# ── 代客申请留学生（approval convert） ────────────────
@router.post("/convert-applies", summary="代客申请留学生（提交至经理审批）")
async def apply_convert(
    data: ConvertApplyCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.apply_convert(current_user.id, data.customer_id, data.approver_id, data.title)
    return success_response(data=ConvertApplyOut(**result), message="已提交经理审批")
