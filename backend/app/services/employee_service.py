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
