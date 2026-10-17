from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.database import get_db
from app.repositories.course_repo import CourseRepository
from app.services.course_service import CourseService

router = APIRouter(prefix="/courses", tags=["课程项目"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CourseService:
    return CourseService(CourseRepository(db))


@router.get("")
async def list_courses(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    category: str | None = Query(None),
    service: CourseService = Depends(_get_service),
):
    return success_response(data=await service.list_courses(page, page_size, category))


@router.get("/{course_id}")
async def get_course(course_id: int, service: CourseService = Depends(_get_service)):
    return success_response(data=await service.get_course(course_id))
