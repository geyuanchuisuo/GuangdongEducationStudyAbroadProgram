"""M4 学生模块路由（v6.8.0）

- /student/* 前缀：学生端（STUDENT-only）
- /employee/students/{id}/progress：进度追踪员工端更新（v2.5.0 契约归 M4，负责员工或 MANAGER）
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.schemas.student import (
    AdminServiceCreate,
    AdminServiceOut,
    AcademicItemOut,
    AcademicOut,
    AgentChatCreate,
    AgentChatOut,
    DdlReminderItem,
    LeaveResultItem,
    LifeFaqOut,
    MoreServicesOut,
    ProgressStageOut,
    ProgressUpdate,
    ProgressUpdateItem,
    PsychChatCreate,
    PsychChatOut,
    PsychProfileOut,
    ReminderCounts,
    RemindersOut,
    ScoreItemOut,
    ServiceItem,
    TicketCreate,
    TicketOut,
    TicketUpdateItem,
)
from app.services.student_service import StudentService

router = APIRouter(prefix="/student", tags=["学生模块"])
employee_router = APIRouter(prefix="/employee/students", tags=["学生模块"])


@router.post("/admin-services")
async def submit_admin_service(
    data: AdminServiceCreate,
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    svc = await StudentService(db).submit_admin_service(current.id, data)
    return success_response(data=AdminServiceOut.model_validate(svc).model_dump(mode="json"))


@router.get("/admin-services")
async def list_admin_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).list_admin_services(current.id, page, page_size)
    result["items"] = [AdminServiceOut.model_validate(i).model_dump(mode="json") for i in result["items"]]
    return success_response(data=result)


@router.post("/psych/chat")
async def psych_chat(
    data: PsychChatCreate,
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).psych_chat(current.id, data.message, data.session_id)
    return success_response(data=PsychChatOut(**result).model_dump())


@router.get("/psych/profile")
async def get_psych_profile(
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    profile = await StudentService(db).get_profile(current.id)
    if profile is None:
        return success_response(data={"latest_emotion_tag": None, "emotion_score": None,
                                      "last_interaction_time": None, "emotion_history": [],
                                      "update_time": None})
    return success_response(data=PsychProfileOut.model_validate(profile).model_dump(mode="json"))


@router.post("/tickets")
async def submit_ticket(
    data: TicketCreate,
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await StudentService(db).submit_ticket(current.id, data)
    return success_response(data=TicketOut.model_validate(ticket).model_dump(mode="json"))


@router.get("/tickets")
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).list_tickets(current.id, page, page_size)
    result["items"] = [TicketOut.model_validate(i).model_dump(mode="json") for i in result["items"]]
    return success_response(data=result)


@router.get("/academic")
async def get_academic(
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).get_academic(current.id)
    return success_response(data=AcademicOut(
        academic_items=[AcademicItemOut.model_validate(i) for i in result["academic_items"]],
        scores=[ScoreItemOut.model_validate(s) for s in result["scores"]],
        score_summary=result["score_summary"],
    ).model_dump(mode="json") | {"upcoming_3d": result["upcoming_3d"]})


@router.get("/progress")
async def get_progress(
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    rows = await StudentService(db).get_progress(current.id)
    return success_response(data=[ProgressStageOut.model_validate(r).model_dump(mode="json") for r in rows])


@employee_router.put("/{student_id}/progress")
async def update_progress(
    student_id: int,
    data: ProgressUpdate,
    current: User = Depends(require_user_type("EMPLOYEE", "MANAGER")),
    db: AsyncSession = Depends(get_db),
):
    row = await StudentService(db).update_progress(current, student_id, data)
    return success_response(data=ProgressStageOut.model_validate(row).model_dump(mode="json"))


@router.get("/life/faq")
async def life_faq(current: User = Depends(require_user_type("STUDENT"))):
    return success_response(data=LifeFaqOut(items=[i for i in StudentService.life_faq()]).model_dump())


@router.get("/services")
async def more_services(current: User = Depends(require_user_type("STUDENT"))):
    return success_response(
        data=MoreServicesOut(items=[ServiceItem(**i) for i in StudentService.more_services()]).model_dump()
    )


# ── 学生助手 Agent（v6.8.1：权限感知注入+限制预期，Dify 不可用降级） ──
@router.post("/agent/chat", summary="学生助手会话（限制预期：不承诺退费/不给出医疗级建议）")
async def agent_chat(
    data: AgentChatCreate,
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).agent_chat(current, data.message, data.session_id)
    return success_response(data=AgentChatOut(**result).model_dump())


@router.post("/agent/chat/stream", summary="学生助手流式会话（SSE 增量下发，v6.11.38）")
async def agent_chat_stream(
    data: AgentChatCreate,
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    """流式学生助手对话（SSE）：event: meta / token / done。

    v6.11.38：感知延迟=首字时间（token 增量下发）；done 事件携带最终数据（reply/session_id/source）。
    流式失败由服务层降级链兜底，前端必收 done；调用方也可回退非流式接口。
    """
    service = StudentService(db)

    async def event_gen():
        async for ev in service.agent_chat_stream(current, data.message, data.session_id):
            name = ev.get("event")
            if name == "token":
                payload = {"delta": ev["delta"]}
            elif name == "meta":
                payload = {"conversation_id": ev["conversation_id"]}
            else:
                payload = ev.get("data") or {}
            yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ── 提醒聚合（v6.8.1：登录拉取即推送，DDL/请假结果/工单结果/进度更新） ──
@router.get("/reminders", summary="登录拉取提醒聚合（学业 DDL/请假结果/工单结果/进度更新）")
async def get_reminders(
    current: User = Depends(require_user_type("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    result = await StudentService(db).get_reminders(current.id)
    return success_response(data=RemindersOut(
        academic_ddl=[DdlReminderItem(**i) for i in result["academic_ddl"]],
        leave_results=[LeaveResultItem(**i) for i in result["leave_results"]],
        ticket_updates=[TicketUpdateItem(**i) for i in result["ticket_updates"]],
        progress_updates=[ProgressUpdateItem(**i) for i in result["progress_updates"]],
        counts=ReminderCounts(**result["counts"]),
    ).model_dump(mode="json"))
