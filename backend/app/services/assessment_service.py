from app.assessment.schemas import AssessmentRecord
from app.models.crm import CustomerAssessment
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.schemas.assessment import AssessmentSaveRequest
from app.schemas.crm import AssessmentOut, CrmLeadCreate
from app.services.crm_service import CrmService


class AssessmentService:
    """研判结果落库服务：把引擎输出映射到 customer_assessment，并按有效性决定是否建档。"""

    def __init__(self, repo: CrmRepository):
        self.repo = repo

    async def save(self, data: AssessmentSaveRequest, current_user: User) -> dict:
        record = data.record
        customer = record.customer or {}
        phone = customer.get("phone")

        lead_id = None
        if record.status == "valid" and phone:
            # valid 自动建档：复用 CrmService.create_lead 的手机号 upsert（去重 + 增量更新）。
            crm_service = CrmService(self.repo)
            lead_result = await crm_service.create_lead(
                CrmLeadCreate(
                    customer_name=customer.get("name") or "未知客户",
                    phone=phone,
                    source="研判",
                    profile=customer,
                ),
                current_user,
            )
            lead_id = lead_result["lead"]["id"]

        assessment = CustomerAssessment(
            customer_name=customer.get("name"),
            source_type=data.source_type,
            source_file=data.source_file,
            phone=phone,
            lead_id=lead_id,
            extracted_info=customer,
            assessment_result=record.model_dump(),
            match_score=None,
            matched_products=record.recommended_projects,
            recommendation=self._build_recommendation(record),
            status="completed",
            employee_id=current_user.id,
            is_valid=record.status == "valid",
            invalid_reason=record.invalid_reason,
        )
        created = await self.repo.create_assessment(assessment)
        return AssessmentOut.model_validate(created).model_dump()

    @staticmethod
    def _build_recommendation(record: AssessmentRecord) -> str | None:
        parts = [part for part in (record.customer_overview, record.follow_up_advice) if part]
        return "\n".join(parts) if parts else None
