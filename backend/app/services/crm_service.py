import logging
import re

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.crm import CrmFollowUp, CrmLead, CustomerAssessment
from app.models.customer import Customer
from app.models.user import User
from app.repositories.crm_repo import CrmRepository
from app.repositories.customer_repo import CustomerRepository
from app.schemas.crm import (
    AssessmentCreate,
    AssessmentOut,
    CrmLeadCreate,
    CrmLeadOut,
    CrmLeadUpdate,
    FollowUpOut,
    LeadFollowUp,
)
from app.services.event_bus import event_bus
from app.services.event_contracts import EventType

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")

LEAD_STATUSES = {"new", "processing", "converted", "invalid"}
LEAD_STATUS_TRANSITIONS = {
    "new": {"processing", "converted", "invalid"},
    "processing": {"converted", "invalid"},
}

# 客户研判画像字段（与 app/assessment/extractors.py CustomerFacts 一致，落在 customer 主表）
CUSTOMER_FACT_FIELDS = (
    "economy",
    "needs",
    "study_intent",
    "german_ability",
    "english_ability",
    "closed_training",
    "criminal_record",
    "belt_and_road",
)


class CrmService:
    def __init__(self, repo: CrmRepository, customer_repo: CustomerRepository):
        self.repo = repo
        self.customer_repo = customer_repo

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

    async def create_lead(self, data: CrmLeadCreate, current_user: User | None = None) -> dict:
        if not data.phone or not PHONE_REGEX.match(data.phone):
            raise ValidationError(message="手机号不合规，需1开头11位大陆手机号")

        owner_id = data.owner_employee_id or (current_user.id if current_user else None)
        customer = await self.customer_repo.get_by_phone(data.phone)
        created_customer = customer is None
        if customer is None:
            customer = Customer(
                phone=data.phone,
                name=data.name,
                gender=data.gender,
                age=data.age,
                education=data.education,
                economy=data.economy,
                needs=data.needs,
                study_intent=data.study_intent,
                german_ability=data.german_ability,
                english_ability=data.english_ability,
                closed_training=data.closed_training,
                criminal_record=data.criminal_record,
                belt_and_road=data.belt_and_road,
                source_channel=data.source,
                owner_employee_id=owner_id,
                status="NEW",
                phone_status="normal",
            )
            customer = await self.customer_repo.create(customer)
        else:
            updates = {}
            for field in ("name", "gender", "age", "education", *CUSTOMER_FACT_FIELDS):
                value = getattr(data, field, None)
                if value is not None:
                    updates[field] = value
            if data.source is not None:
                updates["source_channel"] = data.source
            if updates:
                customer = await self.customer_repo.update(customer, updates)

        lead = CrmLead(
            customer_id=customer.id,
            source=data.source,
            raw_input=data.raw_input,
            background_info=data.background_info,
            status="new",
            owner_employee_id=owner_id,
        )
        created = await self.repo.create_lead(lead)

        if created_customer:
            try:
                await event_bus.publish(
                    EventType.CUSTOMER_REGISTERED,
                    "M1",
                    {
                        "customer_id": customer.id,
                        "phone": customer.phone,
                        "name": customer.name or "未知客户",
                    },
                )
            except Exception:
                logger.exception("发布 customer.registered 事件失败")

        return {"lead": CrmLeadOut.model_validate(created).model_dump(), "created": created_customer}

    async def get_lead(self, lead_id: int, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        return CrmLeadOut.model_validate(lead).model_dump()

    async def update_lead(self, lead_id: int, data: CrmLeadUpdate, current_user: User) -> dict:
        lead = await self._get_owned_lead(lead_id, current_user)
        for field in ("source", "raw_input", "background_info"):
            value = getattr(data, field, None)
            if value is not None:
                setattr(lead, field, value)
        if current_user.user_type == "MANAGER" and data.owner_employee_id is not None:
            lead.owner_employee_id = data.owner_employee_id
        updated = await self.repo.update_lead(lead)

        if lead.customer_id:
            customer = await self.customer_repo.get_by_id(lead.customer_id)
            if customer:
                updates = {}
                for field in ("name", "gender", "age", "education", *CUSTOMER_FACT_FIELDS):
                    value = getattr(data, field, None)
                    if value is not None:
                        updates[field] = value
                if updates:
                    await self.customer_repo.update(customer, updates)

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
        if not lead.customer_id:
            raise ValidationError(message="该线索尚未关联客户，无法添加跟进")
        follow_up = CrmFollowUp(
            customer_id=lead.customer_id,
            employee_id=current_user.id,
            follow_type=data.follow_type,
            content=data.content,
            next_action=data.next_action,
            next_date=data.next_date,
        )
        created = await self.repo.create_follow_up(follow_up)
        return FollowUpOut.model_validate(created).model_dump()

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
            customer_id=data.customer_id,
            batch_no=data.batch_no,
            input_source=data.input_source,
            status=data.status or "valid",
            sg_conclusion=data.sg_conclusion,
            de_conclusion=data.de_conclusion,
            dimensions_json=data.dimensions_json,
            matched_programs_json=data.matched_programs_json,
            recommended_json=data.recommended_json,
            missing_info_json=data.missing_info_json,
            conflicts_json=data.conflicts_json,
            overview=data.overview,
            follow_up_advice=data.follow_up_advice,
            score=data.score,
            prompt_version=data.prompt_version,
            employee_id=data.employee_id or current_user.id,
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
