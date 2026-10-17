from datetime import datetime
from enum import Enum

from sqlalchemy import select

from app.core.exceptions import BusinessError
from app.database import async_session_factory
from app.models.system import ApprovalInstance, ApprovalTask


class ApprovalBizType(str, Enum):
    LEAVE = "leave"
    CONVERT = "convert"
    LATE_REPORT = "late_report"
    COMPLAINT = "complaint"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class ApprovalEngine:
    async def create(
        self,
        biz_type: str | ApprovalBizType,
        initiator_id: int,
        approver_id: int,
        biz_id: int | None = None,
        title: str | None = None,
    ) -> ApprovalInstance:
        biz_str = biz_type.value if isinstance(biz_type, ApprovalBizType) else biz_type

        async with async_session_factory() as session:
            instance = ApprovalInstance(
                biz_type=biz_str,
                biz_id=biz_id,
                title=title,
                initiator_id=initiator_id,
                status=ApprovalStatus.PENDING.value,
                current_step=1,
                total_steps=1,
            )
            session.add(instance)
            await session.flush()

            task = ApprovalTask(
                instance_id=instance.id,
                approver_id=approver_id,
                seq_no=1,
                status=TaskStatus.PENDING.value,
            )
            session.add(task)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def approve(self, instance_id: int, approver_id: int, comment: str | None = None) -> ApprovalInstance:
        return await self._process(instance_id, approver_id, ApprovalStatus.APPROVED, comment)

    async def reject(self, instance_id: int, approver_id: int, comment: str | None = None) -> ApprovalInstance:
        return await self._process(instance_id, approver_id, ApprovalStatus.REJECTED, comment)

    async def _process(
        self,
        instance_id: int,
        approver_id: int,
        status: ApprovalStatus,
        comment: str | None,
    ) -> ApprovalInstance:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ApprovalInstance).where(ApprovalInstance.id == instance_id)
            )
            instance = result.scalar_one_or_none()
            if not instance:
                raise BusinessError(code=40401, message="审批单不存在")
            if instance.status != ApprovalStatus.PENDING.value:
                raise BusinessError(code=40901, message=f"审批单已处理，当前状态: {instance.status}")

            task_result = await session.execute(
                select(ApprovalTask).where(
                    ApprovalTask.instance_id == instance_id,
                    ApprovalTask.seq_no == instance.current_step,
                    ApprovalTask.status == TaskStatus.PENDING.value,
                )
            )
            task = task_result.scalar_one_or_none()
            if not task:
                raise BusinessError(code=40401, message="当前审批任务不存在")
            if task.approver_id != approver_id:
                raise BusinessError(code=40301, message="无权限审批")

            task.action = status.value
            task.comment = comment
            task.acted_at = datetime.now()
            task.status = TaskStatus.COMPLETED.value

            instance.status = status.value
            instance.finished_at = datetime.now()

            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_by_id(self, instance_id: int) -> ApprovalInstance | None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ApprovalInstance).where(ApprovalInstance.id == instance_id)
            )
            return result.scalar_one_or_none()

    async def get_tasks(self, instance_id: int) -> list[ApprovalTask]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ApprovalTask)
                .where(ApprovalTask.instance_id == instance_id)
                .order_by(ApprovalTask.seq_no)
            )
            return list(result.scalars().all())

    async def list_pending_for_approver(self, approver_id: int, biz_type: str | None = None) -> list[ApprovalInstance]:
        async with async_session_factory() as session:
            stmt = (
                select(ApprovalInstance)
                .join(ApprovalTask, ApprovalTask.instance_id == ApprovalInstance.id)
                .where(
                    ApprovalTask.approver_id == approver_id,
                    ApprovalTask.status == TaskStatus.PENDING.value,
                    ApprovalInstance.status == ApprovalStatus.PENDING.value,
                )
            )
            if biz_type:
                stmt = stmt.where(ApprovalInstance.biz_type == biz_type)
            stmt = stmt.order_by(ApprovalInstance.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_by_initiator(self, initiator_id: int) -> list[ApprovalInstance]:
        async with async_session_factory() as session:
            stmt = (
                select(ApprovalInstance)
                .where(ApprovalInstance.initiator_id == initiator_id)
                .order_by(ApprovalInstance.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def batch_approve(self, instance_ids: list[int], approver_id: int, comment: str | None = None) -> list[ApprovalInstance]:
        results = []
        for instance_id in instance_ids:
            result = await self.approve(instance_id, approver_id, comment)
            results.append(result)
        return results


approval_engine = ApprovalEngine()
