from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.schemas.crm import (
    AssessmentCreate,
    CrmLeadCreate,
    CrmLeadUpdate,
    LeadFollowUp,
    LeadStatusChange,
)
from app.services.crm_service import CrmService

router = APIRouter(prefix="/crm", tags=["客户管理"])

current_employee = require_user_type("EMPLOYEE", "MANAGER")


def _get_service(db: AsyncSession = Depends(get_db)) -> CrmService:
    return CrmService(CrmRepository(db))


@router.get("/leads")
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    result = await service.list_leads(page, page_size, current_user, status)
    return success_response(data=result)


@router.post("/leads")
async def create_lead(
    data: CrmLeadCreate,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    result = await service.create_lead(data, current_user)
    message = "创建成功" if result["created"] else "该号码已存在，已增量更新"
    return success_response(data=result, message=message)


@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: int,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.get_lead(lead_id, current_user))


@router.put("/leads/{lead_id}")
async def update_lead(
    lead_id: int,
    data: CrmLeadUpdate,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.update_lead(lead_id, data, current_user), message="更新成功")


@router.patch("/leads/{lead_id}/status")
async def change_lead_status(
    lead_id: int,
    data: LeadStatusChange,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.change_status(lead_id, data.status, current_user), message="状态更新成功")


@router.post("/leads/{lead_id}/follow-ups")
async def add_follow_up(
    lead_id: int,
    data: LeadFollowUp,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.add_follow_up(lead_id, data, current_user), message="跟进记录已添加")


@router.get("/assessments")
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.list_assessments(page, page_size))


@router.post("/assessments")
async def create_assessment(
    data: AssessmentCreate,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.create_assessment(data, current_user), message="研判记录已创建")


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: int,
    current_user: User = Depends(current_employee),
    service: CrmService = Depends(_get_service),
):
    return success_response(data=await service.get_assessment(assessment_id))
