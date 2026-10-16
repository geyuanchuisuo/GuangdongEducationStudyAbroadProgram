from app.core.exceptions import BusinessError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import LoginRequest, LoginResponse, RegisterRequest


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def login(self, request: LoginRequest) -> LoginResponse:
        user = await self.repo.get_by_username(request.username)
        if not user:
            raise BusinessError(code=40001, message="用户名或密码错误")

        if not verify_password(request.password, user.password_hash):
            raise BusinessError(code=40001, message="用户名或密码错误")

        if user.status != "正常":
            raise BusinessError(code=40003, message="账号已被禁用")

        token = create_access_token({"sub": user.id, "type": user.user_type})

        return LoginResponse(
            access_token=token,
            user_id=user.id,
            username=user.username,
            real_name=user.real_name,
            user_type=user.user_type,
        )

    async def register(self, request: RegisterRequest) -> dict:
        existing = await self.repo.get_by_username(request.username)
        if existing:
            raise BusinessError(code=40002, message="用户名已存在")

        user = User(
            username=request.username,
            password_hash=hash_password(request.password),
            real_name=request.real_name,
            user_type=request.user_type,
            contact_info=request.contact_info,
        )
        created = await self.repo.create(user)

        return {"user_id": created.id, "username": created.username}

    async def get_me(self, user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "user_type": user.user_type,
            "employee_role": user.employee_role,
            "department": user.department,
            "contact_info": user.contact_info,
            "status": user.status,
            "create_time": user.create_time,
        }

    async def update_me(self, user: User, data: dict) -> dict:
        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)
        await self.repo.update(user)
        return await self.get_me(user)
