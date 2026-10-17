"""M3 员工模块事件订阅：将外部事件转化为员工待办。

订阅事件：
- customer.registered（M1）：客户注册 → 给 owner_employee 或全员员工生成跟进待办
- psych_alert.created（M4）：心理预警 → 给该学生的负责员工 + 全体 MANAGER 生成紧急待办
"""

import logging
from typing import Any

from sqlalchemy import select

from app.database import async_session_factory
from app.models.customer import Customer
from app.models.employee import EmployeeTodo
from app.models.user import User

logger = logging.getLogger(__name__)


async def _create_todo(
    employee_id: int,
    todo_type: str,
    title: str,
    description: str | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
    priority: str = "medium",
) -> None:
    async with async_session_factory() as session:
        todo = EmployeeTodo(
            employee_id=employee_id,
            todo_type=todo_type,
            title=title,
            description=description,
            related_type=related_type,
            related_id=related_id,
            priority=priority,
            status="pending",
        )
        session.add(todo)
        await session.commit()


async def handle_customer_registered(payload: dict[str, Any]) -> None:
    """customer.registered → 给 owner_employee 生成跟进待办；若无 owner，则给所有 EMPLOYEE 生成。"""
    customer_id = payload.get("customer_id")
    name = payload.get("name") or "新客户"
    phone = payload.get("phone") or ""

    async with async_session_factory() as session:
        owner_id = None
        if customer_id:
            result = await session.execute(select(Customer).where(Customer.id == customer_id))
            customer = result.scalar_one_or_none()
            if customer:
                owner_id = customer.owner_employee_id

        if owner_id:
            employee_ids = [owner_id]
        else:
            result = await session.execute(
                select(User.id).where(User.user_type == "EMPLOYEE", User.status == "正常")
            )
            employee_ids = [row[0] for row in result.all()]

    for emp_id in employee_ids:
        await _create_todo(
            employee_id=emp_id,
            todo_type="customer_follow_up",
            title=f"新客户跟进：{name}（{phone}）",
            description=f"客户ID {customer_id} 注册，请及时跟进",
            related_type="customer",
            related_id=customer_id,
            priority="medium",
        )
    logger.info("customer.registered → 生成 %d 条员工待办（customer_id=%s）", len(employee_ids), customer_id)


async def handle_psych_alert_created(payload: dict[str, Any]) -> None:
    """psych_alert.created → 给全体 MANAGER + 该学生 owner 员工生成高优先级待办。"""
    student_id = payload.get("student_id")
    risk_level = payload.get("risk_level") or "未知"
    reason = payload.get("reason") or ""

    async with async_session_factory() as session:
        # 全体 MANAGER
        result = await session.execute(
            select(User.id).where(User.user_type == "MANAGER", User.status == "正常")
        )
        manager_ids = [row[0] for row in result.all()]

        # 该学生关联的 owner 员工（通过 customer.sys_user_id 反查）
        owner_emp_ids: list[int] = []
        if student_id:
            result = await session.execute(
                select(Customer.owner_employee_id).where(Customer.sys_user_id == student_id)
            )
            owner_emp_ids = [r[0] for r in result.all() if r[0]]

    target_ids = list({*manager_ids, *owner_emp_ids})
    for emp_id in target_ids:
        await _create_todo(
            employee_id=emp_id,
            todo_type="psych_alert",
            title=f"心理预警（{risk_level}）：学生 {student_id}",
            description=f"触发原因：{reason}",
            related_type="student",
            related_id=student_id,
            priority="high",
        )
    logger.info("psych_alert.created → 生成 %d 条紧急待办（student_id=%s）", len(target_ids), student_id)
