from app.core.exceptions import NotFoundError
from app.repositories.course_repo import CourseRepository
from app.schemas.course import CourseOut


class CourseService:
    def __init__(self, repo: CourseRepository):
        self.repo = repo

    async def list_courses(self, page: int, page_size: int, category: str | None = None) -> dict:
        total, items = await self.repo.list_courses(page, page_size, category=category)
        return {"total": total, "items": [CourseOut.model_validate(i).model_dump() for i in items]}

    async def get_course(self, course_id: int) -> dict:
        course = await self.repo.get_course(course_id)
        if not course:
            raise NotFoundError(message="课程不存在")
        return CourseOut.model_validate(course).model_dump()
