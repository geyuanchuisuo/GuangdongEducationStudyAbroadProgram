from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Response
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
    AdminServiceAction,
    AdminServiceOut,
    AnnotationCreate,
    AnnotationOut,
    CommandExecuteCreate,
    CommandExecuteOut,
    CommandParseCreate,
    CommandParseOut,
    ConvertApplyCreate,
    ConvertApplyOut,
    CrmFollowUpCreate,
    CrmFollowUpOut,
    CrmLeadCreate,
    CrmLeadOut,
    CustomerQueryItem,
    CustomerStatusOut,
    CustomerStatusUpdate,
    DailyReportCreate,
    DailyReportDraftUpdate,
    DailyReportOut,
    DailyReportSummaryItem,
    LateApplyCreate,
    LateReviewCreate,
    OralReportCreate,
    OralReportOut,
    OrgNode,
    PasswordChange,
    ProfileUpdate,
    PsychAlertHandle,
    PsychAlertOut,
    ReassignCreate,
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
@router.post("/reports", summary="提交日报（支持草稿）")
async def submit_report(
    data: DailyReportCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    report = await service.submit_report(current_user.id, data.report_date, data.content, data.status)
    msg = "草稿已保存" if data.status == "draft" else "日报已提交"
    return success_response(data=DailyReportOut.model_validate(report), message=msg)


@router.put("/reports/{report_id}", summary="编辑日报草稿")
async def update_draft(
    report_id: int,
    data: DailyReportDraftUpdate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    report = await service.update_draft(report_id, current_user.id, data.content)
    return success_response(data=DailyReportOut.model_validate(report), message="草稿已更新")


@router.post("/reports/{report_id}/late-apply", summary="日报补报申请（草稿+超宽限期→经理审批）")
async def late_apply(
    report_id: int,
    data: LateApplyCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.late_apply(report_id, current_user.id, data.approver_id)
    return success_response(data=result, message="补报申请已提交，待经理审批")


@router.post("/reports/late-review", summary="补报审批（MANAGER）")
async def late_review(
    data: LateReviewCreate,
    current_user: User = Depends(require_user_type("MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.late_review(data.approval_id, current_user.id, data.action, data.comment)
    msg = "补报已通过" if data.action == "approved" else "补报已驳回"
    return success_response(data=result, message=msg)


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


# ── 学生行政服务审批（请假/转班/复学等） ───────────────
@router.get("/admin-services", summary="我需审批的学生行政服务单")
async def list_admin_services(
    status: str | None = Query(None, description="待审批/已通过/已拒绝"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items, total = await service.list_admin_services(current_user.id, status, page, page_size)
    return success_response(
        data={
            "items": [AdminServiceOut.model_validate(s) for s in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/admin-services/{service_id}/review", summary="审批学生行政服务单（走 approval leave）")
async def review_admin_service(
    service_id: int,
    data: AdminServiceAction,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.review_admin_service(
        service_id, current_user.id, data.action, data.comment
    )
    msg = "已批准" if data.action == "approve" else "已拒绝"
    return success_response(data=result, message=msg)


# ── 口述日报（AI 整理） ───────────────────────────────
@router.post("/reports/oral", summary="口述日报（AI 整理，可选落库）")
async def oral_report(
    data: OralReportCreate,
    save: bool = Query(False, description="是否同时落库到 employee_daily_report"),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.generate_oral_report(
        current_user.id, data.raw_text, data.report_date, save=save
    )
    return success_response(data=OralReportOut(**result), message="整理完成")


# ── CRM 客户录入（多格式 + AI 研判） ───────────────────
@router.post("/crm/leads", summary="员工录入客户线索（多格式 + AI 研判）")
async def create_crm_lead(
    data: CrmLeadCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    if not data.raw_text and not data.file_urls:
        from app.core.exceptions import BusinessError
        raise BusinessError(code=40002, message="raw_text 与 file_urls 至少填一项")
    result = await service.create_crm_lead(current_user.id, data.model_dump(exclude_unset=True))
    return success_response(data=CrmLeadOut(**result), message=result["message"])


# ── CRM 跟进记录 ──────────────────────────────────────
@router.post("/crm/follow-ups", summary="新增客户跟进记录")
async def create_follow_up(
    data: CrmFollowUpCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    follow = await service.create_follow_up(current_user.id, data.model_dump(exclude_unset=True))
    return success_response(data=CrmFollowUpOut.model_validate(follow), message="已记录")


@router.get("/crm/follow-ups", summary="我的跟进记录")
async def list_follow_ups(
    customer_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items, total = await service.list_my_follow_ups(current_user.id, customer_id, page, page_size)
    return success_response(
        data={
            "items": [CrmFollowUpOut.model_validate(f) for f in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


# ── 指令式业务处理（AI 解析 + 二次确认） ────────────────
@router.post("/commands/parse", summary="解析自然语言指令为业务动作（返回 token）")
async def parse_command(
    data: CommandParseCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.parse_command(current_user.id, data.text)
    return success_response(data=CommandParseOut(**result), message="解析完成，请确认后执行")


@router.post("/commands/execute", summary="二次确认后执行业务动作")
async def execute_command(
    data: CommandExecuteCreate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.execute_command(current_user.id, data.token, data.confirm)
    return success_response(data=CommandExecuteOut(**result), message=result["message"])


# ── 客户状态机（6 态流转） ────────────────────────────
@router.patch("/customers/{customer_id}/status", summary="更新客户状态（6 态流转，写操作日志）")
async def update_customer_status(
    customer_id: int,
    data: CustomerStatusUpdate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.update_customer_status(
        current_user.id, customer_id, data.status, data.reason
    )
    return success_response(data=CustomerStatusOut(**result), message=f"已更新为「{data.status}」")


# ── 意向客户查询（数据隔离 + 筛选排序） ────────────────
@router.get("/customers", summary="我的客户列表（员工看自己/MANAGER 看全部）")
async def list_my_customers(
    status: str | None = Query(None),
    source_channel: str | None = Query(None),
    score_min: int | None = Query(None, ge=0, le=100),
    sort_by: str = Query("created_at", description="created_at/updated_at/score"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    employee_id = current_user.id if current_user.user_type == "EMPLOYEE" else None
    items, total = await service.list_my_customers(
        employee_id, status, source_channel, score_min, sort_by, page, page_size
    )
    return success_response(
        data={
            "items": [CustomerQueryItem(**item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


# ── 投诉工单处理 ──────────────────────────────────────
@router.get("/tickets", summary="投诉工单列表（员工查看）")
async def list_tickets(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items, total = await service.list_tickets(current_user.id, status, page, page_size)
    return success_response(
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/tickets/{ticket_id}/handle", summary="处理投诉工单（写解决方案）")
async def handle_ticket(
    ticket_id: int,
    solution: str = Body(..., embed=True),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.handle_ticket(current_user.id, ticket_id, solution)
    return success_response(data=result, message="工单已处理")


# ── 心理关怀待办标记 ──────────────────────────────────
@router.post("/psych-alerts/{alert_id}/handle", summary="标记心理预警处理（communicated/referred/resolved）")
async def handle_psych_alert(
    alert_id: int,
    data: PsychAlertHandle,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.handle_psych_alert(current_user.id, alert_id, data.action, data.note)
    return success_response(data=result, message="心理关怀已记录")


# ── 日报批示（MANAGER） ──────────────────────────────
@router.post("/reports/{report_id}/annotations", summary="日报批示（MANAGER）")
async def annotate_report(
    report_id: int,
    data: AnnotationCreate,
    current_user: User = Depends(require_user_type("MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    annotation = await service.annotate_report(report_id, current_user.id, data.content)
    return success_response(data=AnnotationOut.model_validate(annotation), message="批示已添加")


@router.get("/reports/{report_id}/annotations", summary="查看日报批示（仅该员工+MANAGER）")
async def list_annotations(
    report_id: int,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    items = await service.list_annotations(report_id, current_user)
    return success_response(data={"items": [AnnotationOut.model_validate(a) for a in items]})


# ── 客户再分配（MANAGER） ────────────────────────────
@router.post("/customers/reassign", summary="客户再分配（MANAGER 直接生效，写日志+事件）")
async def reassign_customers(
    data: ReassignCreate,
    current_user: User = Depends(require_user_type("MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    result = await service.reassign_customers(
        current_user.id, data.from_employee_id, data.to_employee_id, data.customer_ids
    )
    return success_response(data=result, message=f"已转移 {result['moved']} 个客户")


# ── 个人信息 ────────────────────────────────────────
@router.get("/profile", summary="个人信息")
async def get_profile(current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER"))):
    return success_response(data={
        "id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name,
        "user_type": current_user.user_type,
        "phone": current_user.phone,
        "employee_role": current_user.employee_role,
        "department": current_user.department,
        "contact_info": current_user.contact_info,
    })


@router.put("/profile", summary="修改基本信息（real_name/phone/department/contact_info）")
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    user = await service.update_profile(current_user.id, data.model_dump(exclude_unset=True))
    return success_response(data={"id": user.id, "real_name": user.real_name, "phone": user.phone}, message="已更新")


@router.put("/profile/password", summary="修改密码（需验证旧密码）")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    await service.change_password(current_user.id, data.old_password, data.new_password)
    return success_response(message="密码已修改，请重新登录")


@router.get("/profile/stats", summary="我的客户统计（本月新增/跟进中/已签约/已流失/总数）")
async def profile_stats(
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    return success_response(data=await service.profile_stats(current_user.id))


# ── CSV 导出 ────────────────────────────────────────
def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/export/customers", summary="导出客户列表 CSV（员工看自己/MANAGER全部）")
async def export_customers(
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    csv_text = await service.export_customers_csv(current_user)
    return _csv_response(csv_text, "customers.csv")


@router.get("/export/daily-reports", summary="导出日报 CSV（支持 start/end 日期筛选）")
async def export_daily_reports(
    start: date | None = Query(None),
    end: date | None = Query(None),
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    csv_text = await service.export_reports_csv(current_user, start, end)
    return _csv_response(csv_text, "daily_reports.csv")


@router.get("/export/follow-ups", summary="导出跟进记录 CSV")
async def export_follow_ups(
    current_user: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    service: EmployeeService = Depends(_get_service),
):
    csv_text = await service.export_followups_csv(current_user)
    return _csv_response(csv_text, "follow_ups.csv")
