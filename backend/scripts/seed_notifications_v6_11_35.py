"""v6.11.35：核心管理层账号站内通知补充（幂等）。

背景：sys_notification 归属个人；seed_owner_rebalance 把通知分配给了测试员工/学生，
MANAGER(13810000004) 名下 0 条，管理层"消息中心/提示信息"无提示消息可展示。

幂等：按 (user_id, title) 判重，可重复执行；仅新增通知，不改动既有数据。
执行：docker exec edu-backend /app/.venv/bin/python -m scripts.seed_notifications_v6_11_35
"""

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.system import SysNotification
from app.models.user import User

NOTIFICATIONS = [
    ("approval", "有新的待审批事项", "员工提交的留学生转化申请待你审批，请前往流程审批处理。"),
    ("approval", "审批提醒", "请假与员工流程审批积压提醒，及时处理避免影响学生服务。"),
    ("system", "系统公告：演示数据说明", "当前环境为演示数据（random.seed(42) 可复现），测试账号统一密码 Test@123456。"),
    ("system", "经营看板口径说明", "经营看板展示全域客户/漏斗/审批/投诉/心理预警聚合口径，与智能汇总报告同源。"),
    ("report", "智能报告生成提醒", "新周期智能报告已可生成，前往智能汇总查看客户经营分析与周报。"),
    ("psych", "心理预警关注提醒", "存在待处理的学生心理预警，请关注学生心理状态并跟进处理。"),
    ("daily_report", "员工日报汇总", "员工日报已提交汇总，可在智能汇总查看日报汇总报告。"),
    ("complaint", "投诉工单提醒", "有售后反馈工单待处理，请及时响应避免超时。"),
    ("system", "权限配置提醒", "管理层权限为逐人配置（permissions JSON），可在权限配置页调整。"),
    ("system", "内网穿透演示提示", "启动脚本已自动拉起公网穿透地址，访客可通过该地址注册登录体验。"),
]


async def main() -> None:
    async with async_session_factory() as session:
        manager = (
            await session.execute(select(User).where(User.username == "13810000004"))
        ).scalar_one_or_none()
        if manager is None:
            print("skip: manager account 13810000004 not found")
            return

        existing = {
            title
            for (title,) in (
                await session.execute(
                    select(SysNotification.title).where(SysNotification.user_id == manager.id)
                )
            ).all()
        }
        created = 0
        for ntype, title, content in NOTIFICATIONS:
            if title in existing:
                continue
            session.add(
                SysNotification(
                    user_id=manager.id,
                    type=ntype,
                    title=title,
                    content=content,
                    is_read=False,
                )
            )
            created += 1
        await session.commit()
        print(f"done: manager notifications created={created}, skipped={len(NOTIFICATIONS) - created}")


if __name__ == "__main__":
    asyncio.run(main())
