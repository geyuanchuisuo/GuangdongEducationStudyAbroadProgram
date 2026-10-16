from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])


def _get_service(db: AsyncSession = Depends(get_db)) -> UserService:
    repo = UserRepository(db)
    return UserService(repo)


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    result = await service.get_me(current_user)
    return success_response(data=result)


@router.put("/me")
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    result = await service.update_me(current_user, data.model_dump(exclude_unset=True))
    return success_response(data=result, message="更新成功")
