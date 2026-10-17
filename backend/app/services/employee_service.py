from datetime import date

from app.core.exceptions import BusinessError, ConflictError, ForbiddenError, NotFoundError
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.student import StudentScore
from app.models.user import User
from app.repositories.employee_repo import (
    DailyReportRepository,
    OrgRepository,
    ScoreRepository,
    TodoRepository,
)
from app.services.approval_engine import ApprovalBizType, approval_engine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeService:
    """M3 员工模块业务逻辑。

    注意：
    - 日报唯一约束：(employee_id, report_date)，重复提交返回 40901
    - 代客申请：走 approval_engine.create(biz_type=convert)，经理审批
    - 数据隔离：普通员工只能看/操作自己的日报/待办；成绩按 student_id 查询不限员工
    """

    def __init__(
        self,
        db: AsyncSession,
        report_repo: DailyReportRepository,
        todo_repo: TodoRepository,
        org_repo: OrgRepository,
        score_repo: ScoreRepository,
    ):
        self.db = db
        self.report_repo = report_repo
        self.todo_repo = todo_repo
        self.org_repo = org_repo
        self.score_repo = score_repo

    # ── 日报 ──────────────────────────────────────────
    async def submit_report(self, employee_id: int, report_date: date, content: str) -> EmployeeDailyReport:
        existing = await self.report_repo.get_by_emp_date(employee_id, report_date)
        if existing:
            raise ConflictError(message=f"{report_date} 日报已提交，请勿重复")
        report = EmployeeDailyReport(employee_id=employee_id, report_date=report_date, content=content)
        return await self.report_repo.create(report)

    async def list_my_reports(self, employee_id: int, page: int, page_size: int) -> tuple[list[EmployeeDailyReport], int]:
        return await self.report_repo.list_by_employee(employee_id, page, page_size)

    async def list_all_reports(self, page: int, page_size: int) -> tuple[list[EmployeeDailyReport], int]:
        return await self.report_repo.list_all(page, page_size)

    async def reports_summary(self, start: date | None, end: date | None) -> list[tuple[date, int]]:
        return await self.report_repo.summary_by_date(start, end)

    # ── 待办 ──────────────────────────────────────────
    async def create_todo(self, employee_id: int, data: dict) -> EmployeeTodo:
        todo = EmployeeTodo(employee_id=employee_id, **data)
        return await self.todo_repo.create(todo)

    async def update_todo(self, todo_id: int, employee_id: int, data: dict) -> EmployeeTodo:
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise NotFoundError(message="待办不存在")
        if todo.employee_id != employee_id:
            raise ForbiddenError(message="只能操作自己的待办")
        return await self.todo_repo.update(todo, data)

    async def list_my_todos(
        self, employee_id: int, status: str | None, page: int, page_size: int
    ) -> tuple[list[EmployeeTodo], int]:
        return await self.todo_repo.list_by_employee(employee_id, status, page, page_size)

    # ── 组织架构 ──────────────────────────────────────
    async def get_org_tree(self) -> list[EmployeeOrg]:
        return await self.org_repo.list_all()

    # ── 成绩 ──────────────────────────────────────────
    async def record_score(self, data: dict) -> StudentScore:
        # 验证学生存在且身份为 STUDENT
        result = await self.db.execute(select(User).where(User.id == data["student_id"]))
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(message="学生不存在")
        if student.user_type != "STUDENT":
            raise BusinessError(code=40002, message=f"用户 {data['student_id']} 不是学生")
        score = StudentScore(**data)
        return await self.score_repo.create(score)

    async def list_scores(
        self, student_id: int | None, semester: str | None, page: int, page_size: int
    ) -> tuple[list[StudentScore], int]:
        return await self.score_repo.list_all(student_id, semester, page, page_size)

    # ── 代客申请留学生（approval convert） ─────────────
    async def apply_convert(
        self, employee_id: int, customer_id: int, approver_id: int, title: str | None
    ) -> dict:
        # 客户必须存在
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError(message="客户不存在")

        # 审批人必须是 MANAGER
        result = await self.db.execute(select(User).where(User.id == approver_id))
        approver = result.scalar_one_or_none()
        if not approver:
            raise NotFoundError(message="审批人不存在")
        if approver.user_type != "MANAGER":
            raise BusinessError(code=40002, message="审批人必须是管理层（MANAGER）")

        final_title = title or f"代客申请：{customer.name or customer.phone} → 留学生"
        instance = await approval_engine.create(
            biz_type=ApprovalBizType.CONVERT,
            initiator_id=employee_id,
            approver_id=approver_id,
            biz_id=customer_id,
            title=final_title,
        )
        return {
            "approval_id": instance.id,
            "biz_type": instance.biz_type,
            "biz_id": instance.biz_id,
            "status": instance.status,
        }

    # ── 学生行政服务审批（请假/转班/复学等） ─────────────
    async def list_admin_services(
        self, employee_id: int, status: str | None, page: int, page_size: int
    ) -> tuple[list, int]:
        """员工查询自己作为 approver 的学生行政服务审批单（学生请假等）。"""
        from app.models.student import StudentAdminService
        stmt = select(StudentAdminService).where(StudentAdminService.approver_id == employee_id)
        count_stmt = select(StudentAdminService.id).where(StudentAdminService.approver_id == employee_id)
        if status:
            stmt = stmt.where(StudentAdminService.status == status)
            count_stmt = count_stmt.where(StudentAdminService.status == status)
        total = (await self.db.execute(count_stmt)).all()
        stmt = stmt.order_by(StudentAdminService.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), len(total)

    async def review_admin_service(
        self, service_id: int, employee_id: int, action: str, comment: str | None
    ) -> dict:
        """审批学生行政服务单。走 approval_engine.leave，同步更新 student_admin_service.status。"""
        from app.models.student import StudentAdminService
        result = await self.db.execute(
            select(StudentAdminService).where(StudentAdminService.id == service_id)
        )
        svc = result.scalar_one_or_none()
        if not svc:
            raise NotFoundError(message="审批单不存在")
        if svc.approver_id != employee_id:
            raise ForbiddenError(message="你不是该单的审批人")
        if svc.status != "待审批":
            raise ConflictError(message=f"该单已处理，当前状态：{svc.status}")

        if action not in ("approve", "reject"):
            raise BusinessError(code=40002, message="action 必须是 approve 或 reject")

        # 同步走 approval_engine，biz_id = service.id
        # 先找到对应的 approval_instance（如果学生端已发起），否则现场创建
        from app.models.system import ApprovalInstance
        inst_result = await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.biz_type == ApprovalBizType.LEAVE.value,
                ApprovalInstance.biz_id == service_id,
            )
        )
        instance = inst_result.scalar_one_or_none()
        if instance is None:
            # 学生端未走引擎，员工侧补建（initiator 用学生 id）
            instance = await approval_engine.create(
                biz_type=ApprovalBizType.LEAVE,
                initiator_id=svc.student_id,
                approver_id=employee_id,
                biz_id=service_id,
                title=f"学生{svc.student_id} {svc.service_type} 申请",
            )

        if action == "approve":
            instance = await approval_engine.approve(instance.id, employee_id, comment)
            svc.status = "已通过"
            from app.services.event_bus import event_bus
            from app.services.event_contracts import EventType
            await event_bus.publish(
                EventType.LEAVE_APPROVED,
                source_module="M3",
                payload={"student_id": svc.student_id, "leave_id": svc.id, "status": svc.status},
            )
        else:
            instance = await approval_engine.reject(instance.id, employee_id, comment)
            svc.status = "已拒绝"
            from app.services.event_bus import event_bus
            from app.services.event_contracts import EventType
            await event_bus.publish(
                EventType.LEAVE_REJECTED,
                source_module="M3",
                payload={"student_id": svc.student_id, "leave_id": svc.id, "status": svc.status},
            )

        await self.db.commit()
        return {
            "service_id": svc.id,
            "status": svc.status,
            "approval_id": instance.id,
            "approval_status": instance.status,
        }

    # ── 口述日报（AI 整理） ──────────────────────────────
    async def generate_oral_report(
        self, employee_id: int, raw_text: str, report_date: date | None, save: bool = False
    ) -> dict:
        """调 AI 网关把口述文本整理成结构化日报。

        save=True 时同时落库到 employee_daily_report（沿用唯一约束）。
        """
        from datetime import date as _date
        from app.services.ai_service import AgentType, ai_service

        target_date = report_date or _date.today()
        prompt = (
            "请将以下员工口述内容整理为结构化工作日报，"
            "包含三个部分：一、今日完成事项（按条列出）；二、遇到的问题；三、明日计划。"
            "保持简洁专业，不添加未提及的内容。\n\n"
            f"口述原文：{raw_text}"
        )
        try:
            resp = await ai_service.chat(
                agent=AgentType.EMPLOYEE,
                message=prompt,
                session_id="new",
                user_id=f"employee_{employee_id}",
            )
            structured = resp.content
            session_id = resp.session_id
        except Exception as exc:
            raise BusinessError(code=50002, message=f"AI 整理失败：{exc}") from exc

        saved_id = None
        if save:
            # 沿用日报唯一约束，重复抛 40901
            existing = await self.report_repo.get_by_emp_date(employee_id, target_date)
            if existing:
                raise ConflictError(message=f"{target_date} 日报已存在，请直接修改而非新建")
            report = EmployeeDailyReport(
                employee_id=employee_id,
                report_date=target_date,
                content=structured,
            )
            report = await self.report_repo.create(report)
            saved_id = report.id

        return {
            "raw_text": raw_text,
            "structured": structured,
            "report_date": target_date,
            "session_id": session_id,
            "saved_report_id": saved_id,
        }
