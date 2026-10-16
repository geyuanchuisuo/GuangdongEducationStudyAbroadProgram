from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.schemas.approval import ApprovalAction, ApprovalCreate, ApprovalInstanceOut, ApprovalTaskOut, BatchApprovalRequest
from app.services.approval_engine import approval_engine

router = APIRouter(prefix="/approvals", tags=["审批管理"])


@router.post("", summary="创建审批单")
async def create_approval(
    data: ApprovalCreate,
    current_user: User = Depends(get_current_user),
):
    instance = await approval_engine.create(
        biz_type=data.biz_type,
        initiator_id=current_user.id,
        approver_id=data.approver_id,
        biz_id=data.biz_id,
        title=data.title,
    )
    tasks = await approval_engine.get_tasks(instance.id)
    result = ApprovalInstanceOut.model_validate(instance)
    result.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
    return success_response(data=result, message="审批单已创建")


@router.post("/{instance_id}/approve", summary="审批通过")
async def approve(
    instance_id: int,
    data: ApprovalAction,
    current_user: User = Depends(get_current_user),
):
    instance = await approval_engine.approve(instance_id, current_user.id, data.comment)
    tasks = await approval_engine.get_tasks(instance.id)
    result = ApprovalInstanceOut.model_validate(instance)
    result.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
    return success_response(data=result, message="审批通过")


@router.post("/{instance_id}/reject", summary="审批拒绝")
async def reject(
    instance_id: int,
    data: ApprovalAction,
    current_user: User = Depends(get_current_user),
):
    instance = await approval_engine.reject(instance_id, current_user.id, data.comment)
    tasks = await approval_engine.get_tasks(instance.id)
    result = ApprovalInstanceOut.model_validate(instance)
    result.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
    return success_response(data=result, message="审批拒绝")


@router.post("/batch-approve", summary="批量审批通过")
async def batch_approve(
    data: BatchApprovalRequest,
    current_user: User = Depends(get_current_user),
):
    instances = await approval_engine.batch_approve(data.instance_ids, current_user.id, data.comment)
    results = []
    for inst in instances:
        tasks = await approval_engine.get_tasks(inst.id)
        r = ApprovalInstanceOut.model_validate(inst)
        r.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
        results.append(r)
    return success_response(data=results, message=f"批量审批完成，共 {len(results)} 条")


@router.get("/pending", summary="待审批列表")
async def list_pending(
    biz_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    instances = await approval_engine.list_pending_for_approver(current_user.id, biz_type)
    results = []
    for inst in instances:
        tasks = await approval_engine.get_tasks(inst.id)
        r = ApprovalInstanceOut.model_validate(inst)
        r.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
        results.append(r)
    return success_response(data=results)


@router.get("/my", summary="我发起的审批")
async def list_my(
    current_user: User = Depends(get_current_user),
):
    instances = await approval_engine.list_by_initiator(current_user.id)
    results = []
    for inst in instances:
        tasks = await approval_engine.get_tasks(inst.id)
        r = ApprovalInstanceOut.model_validate(inst)
        r.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
        results.append(r)
    return success_response(data=results)


@router.get("/{instance_id}", summary="审批详情")
async def get_approval(
    instance_id: int,
    current_user: User = Depends(get_current_user),
):
    instance = await approval_engine.get_by_id(instance_id)
    if not instance:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(message="审批单不存在")
    tasks = await approval_engine.get_tasks(instance.id)
    result = ApprovalInstanceOut.model_validate(instance)
    result.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
    return success_response(data=result)
