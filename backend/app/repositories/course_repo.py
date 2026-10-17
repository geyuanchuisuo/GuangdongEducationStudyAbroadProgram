from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseProject


class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_courses(
        self,
        page: int,
        page_size: int,
        category: str | None = None,
    ) -> tuple[int, list[CourseProject]]:
        query = select(CourseProject)
        count_query = select(func.count(CourseProject.id))
        if category is not None:
            query = query.where(CourseProject.category == category)
            count_query = count_query.where(CourseProject.category == category)
        query = query.order_by(CourseProject.id.desc()).offset((page - 1) * page_size).limit(page_size)
        total = (await self.db.execute(count_query)).scalar_one()
        items = (await self.db.execute(query)).scalars().all()
        return total, list(items)

    async def get_course(self, course_id: int) -> CourseProject | None:
        result = await self.db.execute(select(CourseProject).where(CourseProject.id == course_id))
        return result.scalar_one_or_none()
