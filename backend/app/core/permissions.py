from collections.abc import Callable
from functools import wraps
from typing import Any

from sqlalchemy import Select, and_

from app.core.exceptions import ForbiddenError
from app.models.user import User


def require_permission(permission: str):
    def checker(current_user: User) -> User:
        if current_user.user_type in ("ADMIN", "MANAGER"):
            return current_user
        perms = current_user.permissions or []
        if permission not in perms:
            raise ForbiddenError(message=f"缺少权限: {permission}")
        return current_user
    return checker


def data_scope(stmt: Select, current_user: User, model: Any, owner_field: str = "owner_employee_id") -> Select:
    if current_user.user_type in ("ADMIN", "MANAGER"):
        return stmt
    if current_user.user_type == "EMPLOYEE":
        if hasattr(model, owner_field):
            return stmt.where(getattr(model, owner_field) == current_user.id)
    return stmt


def filter_by_department(stmt: Select, current_user: User, model: Any, department_field: str = "department") -> Select:
    if current_user.user_type in ("ADMIN", "MANAGER"):
        return stmt
    if current_user.department:
        if hasattr(model, department_field):
            return stmt.where(getattr(model, department_field) == current_user.department)
    return stmt
