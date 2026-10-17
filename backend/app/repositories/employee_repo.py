from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.student import StudentScore


class DailyReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, report: EmployeeDailyReport) -> EmployeeDailyReport:
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_emp_date(self, employee_id: int, report_date: date) -> EmployeeDailyReport | None:
        result = await self.db.execute(
            select(EmployeeDailyReport).where(
                EmployeeDailyReport.employee_id == employee_id,
                EmployeeDailyReport.report_date == report_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, report_id: int) -> EmployeeDailyReport | None:
        result = await self.db.execute(
            select(EmployeeDailyReport).where(EmployeeDailyReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def update(self, report: EmployeeDailyReport) -> EmployeeDailyReport:
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_by_employee(self, employee_id: int, page: int = 1, page_size: int = 20) -> tuple[list[EmployeeDailyReport], int]:
        stmt = select(EmployeeDailyReport).where(EmployeeDailyReport.employee_id == employee_id)
        total_result = await self.db.execute(
            select(func.count()).select_from(EmployeeDailyReport).where(EmployeeDailyReport.employee_id == employee_id)
        )
        total = total_result.scalar_one()
        stmt = stmt.order_by(EmployeeDailyReport.report_date.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all(self, page: int = 1, page_size: int = 20) -> tuple[list[EmployeeDailyReport], int]:
        stmt = select(EmployeeDailyReport)
        total_result = await self.db.execute(select(func.count()).select_from(EmployeeDailyReport))
        total = total_result.scalar_one()
        stmt = stmt.order_by(EmployeeDailyReport.report_date.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def summary_by_date(self, start: date | None = None, end: date | None = None) -> list[tuple[date, int]]:
        stmt = select(
            EmployeeDailyReport.report_date,
            func.count().label("submitted"),
        ).group_by(EmployeeDailyReport.report_date)
        if start:
            stmt = stmt.where(EmployeeDailyReport.report_date >= start)
        if end:
            stmt = stmt.where(EmployeeDailyReport.report_date <= end)
        stmt = stmt.order_by(EmployeeDailyReport.report_date.desc())
        result = await self.db.execute(stmt)
        return [(row.report_date, row.submitted) for row in result.all()]


class TodoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, todo: EmployeeTodo) -> EmployeeTodo:
        self.db.add(todo)
        await self.db.commit()
        await self.db.refresh(todo)
        return todo

    async def get_by_id(self, todo_id: int) -> EmployeeTodo | None:
        result = await self.db.execute(select(EmployeeTodo).where(EmployeeTodo.id == todo_id))
        return result.scalar_one_or_none()

    async def update(self, todo: EmployeeTodo, data: dict) -> EmployeeTodo:
        for key, value in data.items():
            if hasattr(todo, key):
                setattr(todo, key, value)
        await self.db.commit()
        await self.db.refresh(todo)
        return todo

    async def list_by_employee(
        self, employee_id: int, status: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[EmployeeTodo], int]:
        stmt = select(EmployeeTodo).where(EmployeeTodo.employee_id == employee_id)
        count_stmt = select(func.count()).select_from(EmployeeTodo).where(EmployeeTodo.employee_id == employee_id)
        if status:
            stmt = stmt.where(EmployeeTodo.status == status)
            count_stmt = count_stmt.where(EmployeeTodo.status == status)
        total = (await self.db.execute(count_stmt)).scalar_one()
        # MySQL 不支持 NULLS LAST 语法，用 IS NULL 升降序模拟：NULL 视为最大
        stmt = stmt.order_by(
            EmployeeTodo.due_time.is_(None),
            EmployeeTodo.due_time.asc(),
            EmployeeTodo.create_time.desc(),
        )
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


class OrgRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[EmployeeOrg]:
        result = await self.db.execute(
            select(EmployeeOrg).where(EmployeeOrg.status == "active").order_by(EmployeeOrg.sort_order, EmployeeOrg.id)
        )
        return list(result.scalars().all())


class ScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, score: StudentScore) -> StudentScore:
        self.db.add(score)
        await self.db.commit()
        await self.db.refresh(score)
        return score

    async def list_by_student(self, student_id: int, page: int = 1, page_size: int = 20) -> tuple[list[StudentScore], int]:
        stmt = select(StudentScore).where(StudentScore.student_id == student_id)
        total = (
            await self.db.execute(select(func.count()).select_from(StudentScore).where(StudentScore.student_id == student_id))
        ).scalar_one()
        stmt = stmt.order_by(StudentScore.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all(
        self, student_id: int | None = None, semester: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[StudentScore], int]:
        stmt = select(StudentScore)
        count_stmt = select(func.count()).select_from(StudentScore)
        if student_id:
            stmt = stmt.where(StudentScore.student_id == student_id)
            count_stmt = count_stmt.where(StudentScore.student_id == student_id)
        if semester:
            stmt = stmt.where(StudentScore.semester == semester)
            count_stmt = count_stmt.where(StudentScore.semester == semester)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(StudentScore.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
