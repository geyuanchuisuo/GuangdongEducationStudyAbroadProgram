# -*- coding: utf-8 -*-
"""P0 方案A：种子业务数据归属重分配到测试账号（v6.11.22，LOG-080）。

问题：种子数据按真实组织分散给 user000~115，测试账号（13810000001~4）名下仅 3~12 条，
按数据隔离规则"员工/学生只看自己的"，测试登录观感像"没数据"。

方案A（经用户批准）：把各模块归属（owner/employee_id/student_id/user_id）字段重分配，
使测试账号名下每模块 >= TARGET 条；**只改归属字段，不动任何业务内容**（姓名/金额/日期/状态等原样保留）。

约束处理（唯一索引防撞车，重复自动跳过）：
- employee_daily_report UNIQUE(employee_id, report_date)
- student_score UNIQUE(student_id, course_name, semester)
- student_psych_profile.student_id UNIQUE（一人一档，不动）
- 其余表无唯一约束，按 id 升序确定性搬移，可复现

幂等：已达目标的模块直接跳过，可重复执行无副作用。
仅作用于项目环境 edu-mysql（DATABASE_URL 指向 59000）。
"""
import asyncio
import os

from sqlalchemy import select, update

from app.database import async_session_factory
from app.models.crm import CrmFollowUp, CrmLead
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport, EmployeeTodo
from app.models.student import StudentAcademic, StudentAdminService, StudentFeedbackTicket, StudentScore
from app.models.system import SysNotification

EMP_ID = 3   # 13810000003 EMPLOYEE 测试账号
STU_ID = 2   # 13810000002 STUDENT 测试账号
TARGET = 60  # 每模块目标条数（>= 50 红线，留余量）


async def _rebalance(session, model, owner_col, target_id, target, extra_skip=None):
    """把 model 的 owner_col 重分配到 target_id，直至达到 target 条。

    extra_skip(row, taken) -> bool 为 True 时跳过该行（用于唯一约束避让）。
    返回实际搬移条数。
    """
    cur = (await session.execute(
        select(model.id).where(owner_col == target_id).order_by(model.id)
    )).scalars().all()
    taken = set(cur)
    if len(taken) >= target:
        return 0
    rows = (await session.execute(
        select(model).where(owner_col != target_id).order_by(model.id)
    )).scalars().all()
    moved = 0
    for row in rows:
        if len(taken) >= target:
            break
        if extra_skip and extra_skip(row, taken):
            continue
        await session.execute(update(model).where(model.id == row.id).values({owner_col.key: target_id}))
        taken.add(row.id)
        moved += 1
    return moved


async def main():
    async with async_session_factory() as s:
        # ── 员工侧（EMP_ID=3） ──
        moved = await _rebalance(s, Customer, Customer.owner_employee_id, EMP_ID, TARGET)
        print(f"  customer.owner_employee_id -> 3: +{moved}")
        moved = await _rebalance(s, EmployeeTodo, EmployeeTodo.employee_id, EMP_ID, TARGET)
        print(f"  employee_todo.employee_id -> 3: +{moved}")

        # 日报 UNIQUE(employee_id, report_date)：跳过撞日期的行
        used_dates = set((await s.execute(
            select(EmployeeDailyReport.report_date).where(EmployeeDailyReport.employee_id == EMP_ID)
        )).scalars().all())

        def _skip_report(row, taken):
            if row.report_date in used_dates:
                return True
            used_dates.add(row.report_date)
            return False

        moved = await _rebalance(s, EmployeeDailyReport, EmployeeDailyReport.employee_id, EMP_ID, TARGET,
                                 extra_skip=_skip_report)
        print(f"  employee_daily_report.employee_id -> 3: +{moved}（撞日期行已跳过）")
        moved = await _rebalance(s, CrmFollowUp, CrmFollowUp.employee_id, EMP_ID, TARGET)
        print(f"  crm_follow_up.employee_id -> 3: +{moved}")
        moved = await _rebalance(s, CrmLead, CrmLead.owner_employee_id, EMP_ID, TARGET)
        print(f"  crm_lead.owner_employee_id -> 3: +{moved}")

        # ── 学生侧（STU_ID=2） ──
        # 成绩 UNIQUE(student_id, course_name, semester)
        used_pairs = set((await s.execute(
            select(StudentScore.course_name, StudentScore.semester).where(StudentScore.student_id == STU_ID)
        )).all())

        def _skip_score(row, taken):
            pair = (row.course_name, row.semester)
            if pair in used_pairs:
                return True
            used_pairs.add(pair)
            return False

        moved = await _rebalance(s, StudentScore, StudentScore.student_id, STU_ID, TARGET,
                                 extra_skip=_skip_score)
        print(f"  student_score.student_id -> 2: +{moved}（撞唯一组合行已跳过）")
        moved = await _rebalance(s, StudentFeedbackTicket, StudentFeedbackTicket.student_id, STU_ID, TARGET)
        print(f"  student_feedback_ticket.student_id -> 2: +{moved}")
        moved = await _rebalance(s, StudentAdminService, StudentAdminService.student_id, STU_ID, TARGET)
        print(f"  student_admin_service.student_id -> 2: +{moved}")
        moved = await _rebalance(s, StudentAcademic, StudentAcademic.student_id, STU_ID, TARGET)
        print(f"  student_academic.student_id -> 2: +{moved}")

        # ── 通知（sys_notification.user_id）：员工/学生各 50，池不足时从对方超额中回调 ──
        # 注意两趟不能互抢：趟间排除对方归属，超额时允许从对方搬回（仍只动归属字段）
        async def _rebalance_notifications():
            async def _count(uid):
                return len((await s.execute(
                    select(SysNotification.id).where(SysNotification.user_id == uid)
                )).scalars().all())

            for uid, other in ((EMP_ID, STU_ID), (STU_ID, EMP_ID)):
                cur_ids = set((await s.execute(
                    select(SysNotification.id).where(SysNotification.user_id == uid)
                )).scalars().all())
                if len(cur_ids) >= 50:
                    continue
                cands = (await s.execute(
                    select(SysNotification).where(
                        SysNotification.user_id.notin_([uid, other])
                    ).order_by(SysNotification.id)
                )).scalars().all()
                for row in cands:
                    if len(cur_ids) >= 50:
                        break
                    await s.execute(update(SysNotification).where(SysNotification.id == row.id)
                                    .values(user_id=uid))
                    cur_ids.add(row.id)
            # 双向回调：任一方 < 50 且对方 > 50 时，从对方超额搬回（对方保底 50）
            for uid, other in ((EMP_ID, STU_ID), (STU_ID, EMP_ID)):
                mine = set((await s.execute(
                    select(SysNotification.id).where(SysNotification.user_id == uid)
                )).scalars().all())
                if len(mine) >= 50:
                    continue
                theirs = (await s.execute(
                    select(SysNotification.id).where(SysNotification.user_id == other)
                    .order_by(SysNotification.id)
                )).scalars().all()
                move_n = min(50 - len(mine), len(theirs) - 50)
                for nid in theirs[:max(move_n, 0)]:
                    await s.execute(update(SysNotification).where(SysNotification.id == nid)
                                    .values(user_id=uid))
                    mine.add(nid)
            print(f"  sys_notification -> emp/50,stu/50 均衡完成（emp={await _count(EMP_ID)}, stu={await _count(STU_ID)}）")

        await _rebalance_notifications()

        await s.commit()
    print("rebalance done (idempotent, rerun-safe)")


if __name__ == "__main__":
    asyncio.run(main())
