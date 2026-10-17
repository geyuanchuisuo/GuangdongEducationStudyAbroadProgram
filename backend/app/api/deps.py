from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User
from sqlalchemy import select

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthError()

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise AuthError()

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise AuthError()
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AuthError() from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthError(message="用户不存在")

    if user.status != "正常":
        raise ForbiddenError(message="账号已被禁用")

    return user


def require_user_type(*allowed_types: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.user_type not in allowed_types:
            raise ForbiddenError()
        return current_user
    return checker
