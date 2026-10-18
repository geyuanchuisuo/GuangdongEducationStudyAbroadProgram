import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.customer import Customer
from app.models.user import User
from app.services.event_bus import event_bus
from app.services.event_contracts import EventType

logger = logging.getLogger(__name__)

# 客户转留学生后，客户状态置为「已入学」
CONVERTED_CUSTOMER_STATUS = "ENROLLED"


async def handle_approval_approved(payload: dict) -> None:
    """审批通过后置处理：biz_type==convert 时执行 PROSPECT → STUDENT 身份转换。"""
    biz_type = payload.get("biz_type")
    if biz_type != "convert":
        return

    customer_id = payload.get("biz_id")
    if not customer_id:
        logger.warning("convert 审批通过但缺少 biz_id(customer_id)")
        return

    async with async_session_factory() as session:
        customer = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
        if not customer:
            logger.warning("convert 审批通过但客户不存在: customer_id=%s", customer_id)
            return

        user_id = customer.sys_user_id
        if not user_id:
            logger.warning("客户未关联账号，无法转换身份: customer_id=%s", customer_id)
            return

        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            logger.warning("客户关联账号不存在: customer_id=%s user_id=%s", customer_id, user_id)
            return

        old_type = user.user_type
        if old_type != "PROSPECT":
            logger.info("客户账号非 PROSPECT，跳过身份转换: user_id=%s type=%s", user_id, old_type)
            return

        user.user_type = "STUDENT"
        customer.status = CONVERTED_CUSTOMER_STATUS
        await session.commit()

        logger.info(
            "客户转留学生成功: customer_id=%s user_id=%s %s→STUDENT, status→%s",
            customer_id, user_id, old_type, CONVERTED_CUSTOMER_STATUS,
        )

    # 身份转换完成后发布事件，供 M4 学生端开通、M5 报告更新等消费
    await event_bus.publish(
        EventType.CUSTOMER_CONVERTED_TO_STUDENT,
        source_module="M1",
        payload={"customer_id": customer_id, "student_id": user_id},
    )
