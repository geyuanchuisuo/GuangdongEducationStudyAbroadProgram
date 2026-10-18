from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
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


@router.post("/prospect/approve")
async def approve_prospect(
    approval_id: int,
    action: str,
    comment: str | None = None,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    # v6.10.0：审批人从 JWT 取并校验 MANAGER（替代 v6.9.11 的 query 临时方案）
    if current_user.user_type != "MANAGER":
        raise BusinessError(code=40301, message="仅管理层可审批客户注册")
    result = await service.approve_prospect(approval_id, current_user.id, action, comment)
    return success_response(data=result, message="审批完成")
