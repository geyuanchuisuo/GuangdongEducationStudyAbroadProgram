from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.database import get_db
from app.repositories.user_repo import UserRepository
from app.schemas.user import LoginRequest, RegisterRequest
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["认证"])


def _get_service(db: AsyncSession = Depends(get_db)) -> UserService:
    repo = UserRepository(db)
    return UserService(repo)


@router.post("/login")
async def login(request: LoginRequest, service: UserService = Depends(_get_service)):
    result = await service.login(request)
    return success_response(data=result.model_dump(), message="登录成功")


@router.post("/register")
async def register(request: RegisterRequest, service: UserService = Depends(_get_service)):
    result = await service.register(request)
    return success_response(data=result, message="注册成功")
