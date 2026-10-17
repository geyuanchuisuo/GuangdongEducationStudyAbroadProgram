from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.schemas.assessment import AssessmentSaveRequest
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/crm/assessments", tags=["客户研判"])

current_employee = require_user_type("EMPLOYEE", "MANAGER")


def _get_service(db: AsyncSession = Depends(get_db)) -> AssessmentService:
    return AssessmentService(CrmRepository(db))


@router.post("/save")
async def save_assessment(
    data: AssessmentSaveRequest,
    current_user: User = Depends(current_employee),
    service: AssessmentService = Depends(_get_service),
):
    return success_response(data=await service.save(data, current_user), message="研判记录已保存")
