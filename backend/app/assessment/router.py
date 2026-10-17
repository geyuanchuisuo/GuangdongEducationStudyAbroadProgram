from fastapi import APIRouter, Depends

from app.api.deps import require_user_type
from app.core.response import success_response

from .engine import CustomerAssessmentEngine
from .schemas import AssessmentRequest, BatchAssessmentRequest

router = APIRouter(prefix="/crm/assessments", tags=["客户研判"])
engine = CustomerAssessmentEngine()


@router.post("/text")
async def assess_text(
    request: AssessmentRequest,
    _current_user=Depends(require_user_type("EMPLOYEE", "MANAGER")),
):
    """文本、客服对话或上游已解析的文件文本的单条研判。"""
    return success_response(data=engine.assess_one(request).model_dump())


@router.post("/batch")
async def assess_batch(
    request: BatchAssessmentRequest,
    _current_user=Depends(require_user_type("EMPLOYEE", "MANAGER")),
):
    """批量研判；批内同手机号自动整合，仅返回一条研判记录。"""
    return success_response(data=[record.model_dump() for record in engine.assess_batch(request.records)])
