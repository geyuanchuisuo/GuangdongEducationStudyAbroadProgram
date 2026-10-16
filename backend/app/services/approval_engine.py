from enum import Enum

from app.core.exceptions import BusinessError
from app.database import async_session_factory
from app.models.system import SysApproval


class ApprovalType(str, Enum):
    CONVERT_STUDENT = "convert_student"
    LEAVE = "leave"
    LATE_REPORT = "late_report"
    COMPLAINT_HANDLE = "complaint_handle"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalEngine:
    async def create(
        self,
        approval_type: str | ApprovalType,
        initiator_id: int,
        target_id: int | None = None,
        approver_id: int | None = None,
    ) -> SysApproval:
        type_str = approval_type.value if isinstance(approval_type, ApprovalType) else approval_type

        async with async_session_factory() as session:
            approval = SysApproval(
                approval_type=type_str,
                initiator_id=initiator_id,
                approver_id=approver_id,
                target_id=target_id,
                status=ApprovalStatus.PENDING.value,
            )
            session.add(approval)
            await session.commit()
            await session.refresh(approval)
            return approval

    async def approve(self, approval_id: int, approver_id: int, remark: str | None = None) -> SysApproval:
        return await self._update_status(approval_id, approver_id, ApprovalStatus.APPROVED, remark)

    async def reject(self, approval_id: int, approver_id: int, remark: str | None = None) -> SysApproval:
        return await self._update_status(approval_id, approver_id, ApprovalStatus.REJECTED, remark)

    async def _update_status(
        self,
        approval_id: int,
        approver_id: int,
        status: ApprovalStatus,
        remark: str | None,
    ) -> SysApproval:
        async with async_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(SysApproval).where(SysApproval.id == approval_id))
            approval = result.scalar_one_or_none()
            if not approval:
                raise BusinessError(code=40401, message="审批单不存在")
            if approval.status != ApprovalStatus.PENDING.value:
                raise BusinessError(code=40901, message=f"审批单已处理，当前状态: {approval.status}")

            approval.approver_id = approver_id
            approval.status = status.value
            if remark:
                approval.remark = remark
            await session.commit()
            await session.refresh(approval)
            return approval

    async def get_by_id(self, approval_id: int) -> SysApproval | None:
        async with async_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(select(SysApproval).where(SysApproval.id == approval_id))
            return result.scalar_one_or_none()

    async def list_pending_for_approver(self, approver_id: int, approval_type: str | None = None) -> list[SysApproval]:
        async with async_session_factory() as session:
            from sqlalchemy import select
            stmt = select(SysApproval).where(
                SysApproval.approver_id == approver_id,
                SysApproval.status == ApprovalStatus.PENDING.value,
            )
            if approval_type:
                stmt = stmt.where(SysApproval.approval_type == approval_type)
            stmt = stmt.order_by(SysApproval.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_by_initiator(self, initiator_id: int) -> list[SysApproval]:
        async with async_session_factory() as session:
            from sqlalchemy import select
            stmt = (
                select(SysApproval)
                .where(SysApproval.initiator_id == initiator_id)
                .order_by(SysApproval.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())


approval_engine = ApprovalEngine()
