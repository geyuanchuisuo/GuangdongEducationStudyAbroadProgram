import json
import re

from app.assessment.schemas import AssessmentRecord
from app.models.crm import CustomerAssessment
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.schemas.assessment import AssessmentSaveRequest
from app.schemas.crm import AssessmentOut, CrmLeadCreate
from app.services.crm_service import CrmService

SCORE_BY_CONCLUSION = {"matched": 90, "partial": 70, "pending": 50, "not_matched": 20}


class AssessmentService:
    """研判结果落库服务：把引擎输出映射到 customer_assessment，并按有效性决定是否建档。"""

    def __init__(self, repo: CrmRepository, customer_repo: CustomerRepository):
        self.repo = repo
        self.customer_repo = customer_repo

    async def save(self, data: AssessmentSaveRequest, current_user: User) -> dict:
        record = data.record
        customer = record.customer or {}
        phone = customer.get("phone")

        customer_id = None
        if record.status == "valid" and phone:
            # valid 自动建档：复用 CrmService.create_lead 的手机号 upsert（去重 + 增量更新）。
            crm_service = CrmService(self.repo, self.customer_repo)
            lead_result = await crm_service.create_lead(
                CrmLeadCreate(
                    phone=phone,
                    name=customer.get("name"),
                    gender=customer.get("gender"),
                    age=self._parse_age(customer.get("age")),
                    education=customer.get("education"),
                    source="研判",
                    raw_input=json.dumps(customer, ensure_ascii=False),
                ),
                current_user,
            )
            customer_id = lead_result["lead"]["customer_id"]

        assessment = CustomerAssessment(
            customer_id=customer_id,
            input_source=data.source_type,
            status=record.status,
            sg_conclusion=self._conclusion(record, "singapore"),
            de_conclusion=self._conclusion(record, "germany"),
            dimensions_json=record.assessments,
            matched_programs_json=self._matched_programs(record),
            recommended_json=record.recommended_projects,
            missing_info_json=record.missing_info,
            conflicts_json=record.conflicts,
            overview=record.customer_overview or record.invalid_reason,
            follow_up_advice=record.follow_up_advice,
            score=self._score(record),
            employee_id=current_user.id,
        )
        created = await self.repo.create_assessment(assessment)
        return AssessmentOut.model_validate(created).model_dump()

    @staticmethod
    def _conclusion(record: AssessmentRecord, key: str) -> str | None:
        assessments = record.assessments or {}
        return assessments.get(key, {}).get("conclusion")

    @staticmethod
    def _matched_programs(record: AssessmentRecord) -> dict | None:
        assessments = record.assessments or {}
        if not assessments:
            return None
        return {key: value.get("matched_programs", []) for key, value in assessments.items()}

    @staticmethod
    def _score(record: AssessmentRecord) -> int | None:
        conclusions = [
            SCORE_BY_CONCLUSION[AssessmentService._conclusion(record, key)]
            for key in ("singapore", "germany")
            if AssessmentService._conclusion(record, key) in SCORE_BY_CONCLUSION
        ]
        return max(conclusions) if conclusions else None

    @staticmethod
    def _parse_age(value) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        match = re.search(r"\d+", str(value))
        return int(match.group()) if match else None
