from datetime import datetime

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.crm import (
    LEAD_STATUS_TRANSITIONS,
    LEAD_STATUSES,
    CrmLead,
    CustomerAssessment,
)
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.schemas.crm import (
    AssessmentCreate,
    AssessmentOut,
    CrmLeadCreate,
    CrmLeadOut,
    CrmLeadUpdate,
    LeadFollowUp,
)


class CrmService:
    def __init__(self, repo: CrmRepository):
        self.repo = repo

    async def list_leads(
        self,
        page: int,
        page_size: int,
        current_user: User,
        status: str | None = None,
    ) -> dict:
        owner_filter = None if current_user.user_type == "MANAGER" else current_user.id
        total, items = await self.repo.list_leads(
            page, page_size, owner_employee_id=owner_filter, status=status
        )
        return {"total": total, "items": [CrmLeadOut.model_validate(i).model_dump() for i in items]}

    async def create_lead(self, data: CrmLeadCreate, current_user: User) -> dict:
        if not data.phone:
            raise ValidationError(message="电话号码不能为空")

        existing = await self.repo.get_lead_by_phone(data.phone)
        if existing:
            # 按电话号码去重：已存在则增量更新（不重复建档）。
            self._check_lead_access(existing, current_user)
            for field in ("customer_name", "contact_info", "background_info", "source", "profile"):
                value = getattr(data, field)
                if value is not None:
                    setattr(existing, field, value)
            if current_user.user_type == "MANAGER" and data.owner_employee_id is not None:
                existing.owner_employee_id = data.owner_employee_id
            updated = await self.repo.update_lead(existing)
            return {"lead": CrmLeadOut.model_validate(updated).model_dump(), "created": False}

        lead = CrmLead(
            customer_name=data.customer_name,
            phone=data.phone,
            contact_info=data.contact_info,
            background_info=data.background_info,
            source=data.source or "客服",
            profile=data.profile,
            owner_employee_id=data.owner_employee_id or current_user.id,
        )
        created = await self.repo.create_lead(lead)
        return {"lead": CrmLeadOut.model_validate(created).model_dump(), "created": True}

    async def get_lead(self, lead_id: int, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        return CrmLeadOut.model_validate(lead).model_dump()

    async def update_lead(self, lead_id: int, data: CrmLeadUpdate, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        for field in ("customer_name", "phone", "contact_info", "background_info", "source", "profile"):
            value = getattr(data, field)
            if value is not None:
                setattr(lead, field, value)
        if current_user.user_type == "MANAGER" and data.owner_employee_id is not None:
            lead.owner_employee_id = data.owner_employee_id
        updated = await self.repo.update_lead(lead)
        return CrmLeadOut.model_validate(updated).model_dump()

    async def change_status(self, lead_id: int, target: str, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        if target not in LEAD_STATUSES:
            raise ValidationError(message=f"非法状态：{target}")
        allowed = LEAD_STATUS_TRANSITIONS.get(lead.status, ())
        if target not in allowed:
            raise ValidationError(message=f"状态不能从「{lead.status}」流转到「{target}」")
        lead.status = target
        updated = await self.repo.update_lead(lead)
        return CrmLeadOut.model_validate(updated).model_dump()

    async def add_follow_up(self, lead_id: int, data: LeadFollowUp, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        history = lead.follow_up_history or []
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "content": data.content,
                "follow_up_type": data.follow_up_type,
                "remark": data.remark,
                "time": datetime.now().isoformat(),
                "operator_id": current_user.id,
            }
        )
        lead.follow_up_history = history
        updated = await self.repo.update_lead(lead)
        return CrmLeadOut.model_validate(updated).model_dump()

    async def list_assessments(self, page: int, page_size: int) -> dict:
        total, items = await self.repo.list_assessments(page, page_size)
        return {"total": total, "items": [AssessmentOut.model_validate(i).model_dump() for i in items]}

    async def get_assessment(self, assessment_id: int) -> dict:
        assessment = await self.repo.get_assessment(assessment_id)
        if not assessment:
            raise NotFoundError(message="研判记录不存在")
        return AssessmentOut.model_validate(assessment).model_dump()

    async def create_assessment(self, data: AssessmentCreate, current_user: User) -> dict:
        assessment = CustomerAssessment(
            customer_name=data.customer_name,
            source_type=data.source_type,
            source_file=data.source_file,
            extracted_info=data.extracted_info,
            assessment_result=data.assessment_result,
            match_score=data.match_score,
            matched_products=data.matched_products,
            recommendation=data.recommendation,
            status=data.status or "pending",
            employee_id=data.employee_id or current_user.id,
            is_valid=data.is_valid,
            invalid_reason=data.invalid_reason,
        )
        created = await self.repo.create_assessment(assessment)
        return AssessmentOut.model_validate(created).model_dump()

    async def _get_owned_lead(self, lead_id: int, current_user: User) -> CrmLead:
        lead = await self.repo.get_lead(lead_id)
        if not lead:
            raise NotFoundError(message="线索不存在")
        self._check_lead_access(lead, current_user)
        return lead

    def _check_lead_access(self, lead: CrmLead, current_user: User) -> None:
        if current_user.user_type != "MANAGER" and lead.owner_employee_id != current_user.id:
            raise ForbiddenError(message="无权访问该线索")
