"""
种子数据脚本 — 生成演示数据
每类表 >= 50 条（部分关联表按实际业务量生成）

特性：
- 幂等可重跑：drop_all + create_all，每次执行重建全库
- 可复现：random.seed(42) 固定随机序列，同一份代码生成完全相同的数据
- 固定测试账号：4 个核心角色（PROSPECT/STUDENT/EMPLOYEE/MANAGER）使用固定手机号作 username，
  密码统一 Test@123456，其他分支合并后可直接用这些账号登录测试
- 全部用户密码统一为 Test@123456

用法:
  容器内: docker exec edu-backend python -m scripts.seed_data
  本地:   cd backend && .venv/Scripts/python -m scripts.seed_data
"""
import asyncio
import random
from datetime import date, datetime, timedelta
from itertools import product

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models import Base
from app.models.crm import (
    AiReport,
    AiReportAttachment,
    CrmFollowUp,
    CrmLead,
    CustomerAssessment,
    TicketAIAnalysis,
)
from app.models.customer import Customer, PendingLead
from app.models.customer_service import CsChatMessage, CsChatSession, CsFaq, CsIntentLog, CsRecommendLog
from app.models.employee import EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.event import EventLecture, EventRegistration
from app.models.student import (
    StudentAcademic,
    StudentAdminService,
    StudentApplicationProgress,
    StudentFeedbackTicket,
    StudentPsychAlert,
    StudentPsychProfile,
    StudentScore,
)
from app.models.system import ApprovalInstance, ApprovalTask, SysEvent, SysNotification, SysOperationLog
from app.models.user import User
from app.core.security import hash_password

# 固定随机种子，保证同一份代码生成完全相同的数据（可复现、可对比）
random.seed(42)

# 统一测试密码（所有账号均使用此密码，便于跨分支/跨环境登录）
TEST_PASSWORD = "Test@123456"

# 权限位：与 seed_supplement_v6_11_13.py 的 PERMS 逐字对齐
# （ADMIN/MANAGER/EMPLOYEE 三组并集；前端 RoleWorkspace.vue 的 permissionOptions 依赖这些 key）
# 不写进这里的话，drop_all 重建后 sys_user.permissions 全为 NULL，权限配置页永远勾不上任何项
USER_PERMISSIONS = {
    "ADMIN": ["system:manage", "user:manage", "report:view", "report:export", "approval:manage"],
    "MANAGER": ["report:view", "report:export", "approval:manage", "employee:manage", "customer:view"],
    "EMPLOYEE": ["customer:edit", "report:daily", "todo:view"],
}

# 4 个核心角色固定账号（手机号即 username），与 docs/测试账号.md 及 scripts/create_frontend_test_accounts.py 对齐
CORE_ACCOUNTS = [
    # (username, user_type, real_name, employee_role, department)
    ("13810000001", "PROSPECT", "意向客户_张敏", None, None),
    ("13810000002", "STUDENT", "留学生_李娜", None, None),
    ("13810000003", "EMPLOYEE", "员工_王强", "普通员工", "咨询部"),
    ("13810000004", "MANAGER", "管理层_赵总", "管理层", "总裁办"),
]

NAMES = [
    "张伟", "王芳", "李娜", "刘洋", "陈杰", "杨秀英", "黄勇", "赵敏", "周杰", "吴丽",
    "徐强", "孙燕", "胡明", "朱红", "高峰", "林静", "何磊", "郭婷", "马超", "罗慧",
    "梁波", "宋霞", "郑鹏", "谢玲", "韩超", "唐军", "冯梅", "于洁", "董刚", "萧瑶",
    "程亮", "曹琳", "袁帅", "邓丽", "许强", "傅芳", "沈杰", "曾华", "彭涛", "吕娜",
    "苏翔", "卢婷", "蒋伟", "蔡娟", "贾明", "丁玲", "魏强", "薛萍", "叶磊", "阎静",
]

DEPARTMENTS = ["咨询部", "教务部", "学生管理部", "市场部", "行政部"]
COURSE_NAMES = [
    "雅思基础班", "雅思强化班", "托福入门班", "托福提高班", "SAT预备班",
    "A-Level数学", "A-Level物理", "AP微积分", "AP经济学", "IB全科辅导",
    "英语口语精品班", "学术写作班", "留学规划课", "背景提升项目", "面试技巧班",
]
LOCATIONS = ["广州总部教室A", "广州总部教室B", "深圳分部教室", "线上直播", "东莞教学点"]

# v6.10.6：演示意图码统一到后端契约 9 码（原 5 码为 seed 遗留词汇，与契约/Dify 均不一致）
INTENT_TYPES = ["program_consult", "course_recommend", "policy_qa", "company_info", "event_query", "faq", "chitchat", "lead_capture"]
SOURCE_CHANNELS = ["WEBSITE_REGISTER", "CS_LEAD", "EMPLOYEE_INPUT"]
CUSTOMER_STATUSES = ["NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST"]
EDUCATION_LEVELS = ["初中", "高中", "大专", "专科", "本科", "其他"]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # ── Users（120 个，前 4 个为固定核心账号，密码统一 Test@123456） ──
        users = []
        # 1. 核心角色账号（固定 username=手机号，密码统一）
        for username, ut, name, role, dept in CORE_ACCOUNTS:
            u = User(
                username=username,
                password_hash=hash_password(TEST_PASSWORD),
                real_name=name,
                user_type=ut,
                phone=username,
                employee_role=role,
                department=dept,
                permissions=USER_PERMISSIONS.get(ut),
                status="正常",
            )
            session.add(u)
            users.append(u)

        # 2. 其余用户：username 固定 user000~user115，密码统一 Test@123456
        other_user_types = ["ADMIN", "MANAGER", "EMPLOYEE", "EMPLOYEE", "EMPLOYEE",
                            "STUDENT", "STUDENT", "PROSPECT"]
        for i in range(116):
            ut = other_user_types[i % len(other_user_types)]
            name = NAMES[i % len(NAMES)]
            u = User(
                username=f"user{i:03d}",
                password_hash=hash_password(TEST_PASSWORD),
                real_name=name,
                user_type=ut,
                # 手机号固定段，避免冲突且可预测
                phone=f"139{i:08d}"[:11],
                employee_role="普通员工" if ut == "EMPLOYEE" else ("管理层" if ut == "MANAGER" else ("管理员" if ut == "ADMIN" else None)),
                department=random.choice(DEPARTMENTS) if ut in ("EMPLOYEE", "MANAGER", "ADMIN") else None,
                permissions=USER_PERMISSIONS.get(ut),
                status="正常",
            )
            session.add(u)
            users.append(u)
        await session.flush()

        admin_ids = [u.id for u in users if u.user_type == "ADMIN"]
        employee_ids = [u.id for u in users if u.user_type == "EMPLOYEE"]
        manager_ids = [u.id for u in users if u.user_type == "MANAGER"]
        student_ids = [u.id for u in users if u.user_type == "STUDENT"]
        prospect_ids = [u.id for u in users if u.user_type == "PROSPECT"]

        # ── Customer 主表 ──
        customers = []
        for i in range(120):
            c = Customer(
                phone=f"138{random.randint(10000000, 99999999)}",
                name=NAMES[i % len(NAMES)] + f"_{i}",
                gender=random.choice(["男", "女"]),
                age=random.randint(16, 45),
                education=random.choice(EDUCATION_LEVELS),
                source_channel=random.choice(SOURCE_CHANNELS),
                owner_employee_id=random.choice(employee_ids),
                status=random.choice(CUSTOMER_STATUSES),
                phone_status="normal",
                first_register_at=datetime.now() - timedelta(days=random.randint(0, 180)),
                sys_user_id=random.choice(prospect_ids) if i < len(prospect_ids) else None,
            )
            session.add(c)
            customers.append(c)
        await session.flush()

        customer_ids = [c.id for c in customers]

        # ── PendingLead（待补全线索） ──
        for i in range(15):
            session.add(PendingLead(
                wechat=f"wx_{i}",
                name=NAMES[i % len(NAMES)] + f"_pending_{i}",
                raw_info=f"原始信息_{i}",
                status="pending",
            ))

        # ── M1: CRM 线索 ──
        for i in range(110):
            lead = CrmLead(
                customer_id=random.choice(customer_ids),
                source=random.choice(["website", "cs", "employee"]),
                raw_input=f"原始录入信息_{i}",
                background_info=f"背景信息_{i}",
                status=random.choice(["new", "processing", "converted", "invalid"]),
                owner_employee_id=random.choice(employee_ids),
            )
            session.add(lead)
        await session.flush()

        for i in range(150):
            session.add(CustomerAssessment(
                customer_id=random.choice(customer_ids),
                batch_no=f"BATCH_{i // 10}",
                input_source=random.choice(["text", "file", "chat"]),
                status=random.choice(["valid", "invalid_input", "invalid_phone"]),
                sg_conclusion=random.choice(["matched", "partial", "pending", "not_matched"]),
                de_conclusion=random.choice(["matched", "partial", "pending", "not_matched"]),
                score=random.choice([90, 70, 50, 20]),
                overview=f"客户速览_{i}",
                follow_up_advice=f"跟进建议_{i}",
                prompt_version="JUDGE-v1.0",
                employee_id=random.choice(employee_ids),
            ))

        for i in range(120):
            session.add(CrmFollowUp(
                customer_id=random.choice(customer_ids),
                employee_id=random.choice(employee_ids),
                follow_type=random.choice(["电话", "微信", "面谈", "邮件"]),
                content=f"跟进内容_{i}",
                next_action=f"下一步_{i}",
                # v6.11.14：约 1/3 落到今天或已过期，保证「客户跟进提醒」follow_ups_due > 0
                # （原实现全为未来日期 → 员工/管理层首页该卡片永远显示 0）
                next_date=datetime.now() + timedelta(days=random.randint(-20, 20)),
            ))

        # 核心员工账号（13810000003）固定补 3 条已到期跟进：随机分配无法保证命中，
        # 否则员工首页「客户跟进提醒」在演示时仍可能为 0
        core_employee_id = users[2].id
        for i in range(3):
            session.add(CrmFollowUp(
                customer_id=random.choice(customer_ids),
                employee_id=core_employee_id,
                follow_type="电话",
                content=f"到期回访_{i}",
                next_action="回访确认最新意向",
                next_date=datetime.now() - timedelta(days=i),
            ))

        # ── M2: CS ──
        for i in range(105):
            session.add(CsFaq(
                category=random.choice(["课程", "费用", "留学", "活动", "生活"]),
                question=f"常见问题_{i}？",
                answer=f"这是问题_{i}的回答。",
                keywords=f"关键词{i},faq{i}",
                sort_order=i,
            ))

        sessions = []
        for i in range(110):
            s = CsChatSession(
                user_id=random.choice(prospect_ids + student_ids),
                customer_id=random.choice(customer_ids) if random.random() > 0.3 else None,
                agent_type=random.choice(["CUSTOMER", "STUDENT", "EMPLOYEE"]),
                status=random.choice(["active", "closed"]),
                title=f"会话_{i}",
            )
            session.add(s)
            sessions.append(s)
        await session.flush()

        for i in range(200):
            session.add(CsChatMessage(
                session_id=random.choice([s.id for s in sessions]),
                role=random.choice(["user", "assistant"]),
                content=f"消息内容_{i}",
                intent=random.choice(INTENT_TYPES) if random.random() > 0.5 else None,
            ))

        for i in range(100):
            session.add(CsIntentLog(
                session_id=random.choice([s.id for s in sessions]),
                user_id=random.choice(prospect_ids),
                customer_id=random.choice(customer_ids) if random.random() > 0.3 else None,
                intent_type=random.choice(INTENT_TYPES),
                confidence=round(random.uniform(0.5, 1.0), 2),
                converted=random.random() > 0.7,
            ))

        # ── Events ──
        events = []
        for i in range(20):
            ev = EventLecture(
                event_name=f"活动/讲座_{i}",
                event_type=random.choice(["讲座", "开放日", "说明会", "沙龙"]),
                start_time=datetime.now() + timedelta(days=random.randint(-30, 60)),
                end_time=datetime.now() + timedelta(days=random.randint(1, 90)),
                location=random.choice(LOCATIONS),
                max_participants=random.choice([30, 50, 100, 200]),
                current_participants=random.randint(0, 50),
                description=f"活动描述_{i}",
                status=random.choice(["报名中", "已满员", "已结束"]),
            )
            session.add(ev)
            events.append(ev)
        await session.flush()

        reg_users = prospect_ids + student_ids
        for i in range(100):
            session.add(EventRegistration(
                event_id=events[i % len(events)].id,
                user_id=reg_users[i % len(reg_users)],
                status=random.choice(["已报名", "已签到", "已取消"]),
            ))

        # ── Courses ──
        from app.models.course import CourseProject
        courses = []
        for i in range(15):
            cp = CourseProject(
                project_name=COURSE_NAMES[i % len(COURSE_NAMES)],
                category=random.choice(["语言培训", "学科辅导", "留学规划", "背景提升"]),
                description=f"课程描述_{i}",
                tuition_fee=random.randint(5000, 50000),
                duration=f"{random.randint(1, 12)}个月",
                status="上架",
            )
            session.add(cp)
            courses.append(cp)
        await session.flush()

        # ── CS 推荐日志（客服 Agent 每次课程/活动推荐落库） ──
        for i in range(150):
            s = sessions[i % len(sessions)]
            kind = random.choices(["course", "event", "other"], weights=[5, 3, 1])[0]
            if kind == "course":
                course = random.choice(courses)
                session.add(CsRecommendLog(
                    session_id=s.id,
                    customer_id=s.customer_id,
                    course_id=course.id,
                    event_id=None,
                    recommendation_type="course",
                    item_name=course.project_name,
                ))
            elif kind == "event":
                ev = random.choice(events)
                session.add(CsRecommendLog(
                    session_id=s.id,
                    customer_id=s.customer_id,
                    course_id=None,
                    event_id=ev.id,
                    recommendation_type="event",
                    item_name=ev.event_name,
                ))
            else:
                session.add(CsRecommendLog(
                    session_id=s.id,
                    customer_id=s.customer_id,
                    course_id=None,
                    event_id=None,
                    recommendation_type="other",
                    item_name=random.choice(["留学规划套餐", "一对一面试辅导", "背景提升项目"]),
                ))

        # ── M3: Employee ──
        for i in range(10):
            session.add(EmployeeOrg(
                name=f"{DEPARTMENTS[i % len(DEPARTMENTS)]}{'_子部门' if i >= 5 else ''}",
                parent_id=None if i < 5 else 1,
                org_type="department",
                sort_order=i,
            ))

        # employee_id+report_date 为唯一约束：按员工轮转、天数递增，保证组合唯一
        for i in range(120):
            session.add(EmployeeDailyReport(
                employee_id=employee_ids[i % len(employee_ids)],
                report_date=date.today() - timedelta(days=i // len(employee_ids)),
                content=f"日报内容_{i}",
            ))

        for i in range(100):
            session.add(EmployeeTodo(
                employee_id=random.choice(employee_ids + manager_ids),
                todo_type=random.choice(["follow_up", "approval", "review", "meeting"]),
                title=f"待办事项_{i}",
                status=random.choice(["pending", "in_progress", "done"]),
                priority=random.choice(["low", "medium", "high"]),
                due_time=datetime.now() + timedelta(days=random.randint(-5, 30)),
            ))

        # student_id+course_name+semester 为唯一约束：从全部组合中随机取 100 条，保证不重复
        score_combos = list(product(student_ids, COURSE_NAMES, ["2026春季", "2026秋季"]))
        random.shuffle(score_combos)
        for sid, cname, sem in score_combos[:100]:
            session.add(StudentScore(
                student_id=sid,
                course_name=cname,
                score=round(random.uniform(40, 100), 1),
                semester=sem,
            ))

        # ── M4: Student ──
        for i in range(100):
            session.add(StudentAdminService(
                student_id=random.choice(student_ids),
                service_type=random.choice(["请假", "休学", "复学", "转班"]),
                reason=f"申请原因_{i}",
                status=random.choice(["待审批", "已批准", "已拒绝"]),
                approver_id=random.choice(employee_ids),
            ))

        # student_id 为唯一约束，每个学生一条画像
        for sid in student_ids:
            session.add(StudentPsychProfile(
                student_id=sid,
                latest_emotion_tag=random.choice(["平稳", "焦虑", "低落", "积极"]),
                emotion_score=random.randint(40, 100),
            ))

        for i in range(100):
            session.add(StudentPsychAlert(
                student_id=random.choice(student_ids),
                risk_level=random.choice(["低", "中", "高"]),
                trigger_reason=f"预警原因_{i}",
                status=random.choice(["未处理", "处理中", "已关闭"]),
                teacher_id=random.choice(employee_ids + manager_ids),
            ))

        tickets = []
        for i in range(100):
            t = StudentFeedbackTicket(
                student_id=random.choice(student_ids),
                content=f"反馈工单_{i}",
                detail=f"工单内容_{i}",
                status=random.choice(["待处理", "处理中", "已解决"]),
            )
            session.add(t)
            tickets.append(t)
        await session.flush()

        # ── 投诉工单 AI 分析（只引用 M4 工单ID，不建外键） ──
        for i, t in enumerate(tickets):
            if i % 5 == 4:
                continue  # 约 80% 工单已有 AI 分析留痕
            roll = random.random()
            status = "succeeded" if roll < 0.85 else ("pending" if roll < 0.95 else "failed")
            done = status == "succeeded"
            session.add(TicketAIAnalysis(
                ticket_id=t.id,
                category=random.choice(["投诉", "建议", "咨询"]) if done else None,
                low_satisfaction_candidate=bool(random.random() > 0.7) if done else False,
                high_risk=bool(random.random() > 0.85) if done else False,
                summary=f"工单 {t.id} 的 AI 归纳摘要（不含原文）" if done else None,
                special_reason=("多次投诉，列为特别案例" if (done and random.random() > 0.9) else None),
                model_source="dify" if done else None,
                prompt_version="TICKET-ANALYSIS-v1.0" if done else None,
                raw_output='{"category":"投诉"}' if done else None,
                status=status,
                error_message="LLM 调用超时" if status == "failed" else None,
                analyzed_at=(datetime.now() - timedelta(days=random.randint(0, 30))) if done else None,
            ))

        for i in range(100):
            session.add(StudentAcademic(
                student_id=random.choice(student_ids),
                item_type=random.choice(["考试", "作业", "选课", "成绩"]),
                title=f"学业事项_{i}",
                course_name=random.choice(COURSE_NAMES),
                due_time=datetime.now() + timedelta(days=random.randint(-30, 30)),
            ))

        for i in range(100):
            session.add(StudentApplicationProgress(
                student_id=random.choice(student_ids),
                stage=random.choice(["材料准备", "申请递交", "面试", "签证", "行前准备"]),
                status=random.choice(["in_progress", "completed", "waiting"]),
            ))

        # ── M5: Reports（20 条，version 递增确保 uq_ai_report_version 唯一约束不冲突） ──
        reports = []
        for i in range(20):
            r = AiReport(
                report_type=random.choice(["daily", "weekly", "monthly", "psych", "business"]),
                report_title=f"报告_{i}",
                status=random.choice(["generating", "completed", "failed"]),
                generated_by=random.choice(manager_ids),
                time_range_start=datetime.now() - timedelta(days=random.randint(1, 30)),
                time_range_end=datetime.now(),
                version=i + 1,
            )
            session.add(r)
            reports.append(r)
        await session.flush()

        # ── 报告附件 ──
        for r in reports:
            for j in range(random.randint(1, 2)):
                ft = random.choice(["pdf", "xlsx", "png"])
                session.add(AiReportAttachment(
                    report_id=r.id,
                    file_path=f"/data/reports/{r.id}/attachment_{j}.{ft}",
                    file_type=ft,
                ))

        # ── M0: System ──
        event_types = [
            "customer.registered", "customer.converted_to_student",
            "leave.approved", "leave.rejected", "psych_alert.created",
            "complaint.resolved", "lead.transferred",
        ]
        for i in range(100):
            session.add(SysEvent(
                event_type=random.choice(event_types),
                source_module=random.choice(["M1", "M2", "M3", "M4"]),
                payload={"index": i, "data": f"event_payload_{i}"},
                status=random.choice(["pending", "consumed", "failed"]),
            ))

        # ── 审批（双表设计） ──
        approval_instances = []
        for i in range(100):
            inst = ApprovalInstance(
                biz_type=random.choice(["leave", "convert", "late_report", "complaint"]),
                biz_id=random.randint(1, 500),
                title=f"审批标题_{i}",
                initiator_id=random.choice(employee_ids + student_ids),
                status=random.choice(["pending", "approved", "rejected"]),
                current_step=1,
                total_steps=1,
            )
            session.add(inst)
            approval_instances.append(inst)
        await session.flush()

        for inst in approval_instances:
            session.add(ApprovalTask(
                instance_id=inst.id,
                approver_id=random.choice(manager_ids),
                seq_no=1,
                action=random.choice(["approved", "rejected"]) if inst.status != "pending" else None,
                comment=f"审批意见_{inst.id}",
                status="completed" if inst.status != "pending" else "pending",
            ))

        for i in range(100):
            session.add(SysNotification(
                user_id=random.choice([u.id for u in users]),
                type=random.choice(["approval", "todo", "academic", "psych_alert", "status", "system"]),
                title=f"通知标题_{i}",
                content=f"通知内容_{i}",
                is_read=random.random() > 0.5,
            ))

        # 核心演示账号固定补站内通知（含未读/已读两种）：
        # 随机分配命中概率低，会导致管理层「消息中心」长期为空、标记已读无处验证
        core_notifications = [
            # (接收人, 类型, 标题, 内容, 是否已读)
            (users[3].id, "approval", "有 3 条日报补报待审批", "员工提交的日报补报申请已进入你的审批队列", False),
            (users[3].id, "todo", "今日有客户待跟进", "请到「客户经营」按最后跟进时间查看明细", False),
            (users[3].id, "system", "系统已更新到 v6.11.14", "本次更新修复了消息中心与客户跟进提醒", True),
            (users[2].id, "todo", "你有一条待办即将到期", "请在今天内处理「客户回访」待办", False),
            (users[2].id, "status", "客户状态已变更", "你负责的客户已流转为「意向强烈」", True),
        ]
        for uid, ntype, title, content, is_read in core_notifications:
            session.add(SysNotification(
                user_id=uid,
                type=ntype,
                title=title,
                content=content,
                is_read=is_read,
            ))

        for i in range(100):
            session.add(SysOperationLog(
                user_id=random.choice([u.id for u in users]),
                module=random.choice(["auth", "crm", "cs", "employee", "student", "report"]),
                action=random.choice(["create", "update", "delete", "login", "export"]),
                target_type="customer",
                target_id=random.choice(customer_ids),
                ip_address=f"192.168.1.{random.randint(1, 254)}",
            ))

        await session.commit()

    print("=" * 60)
    print("种子数据生成完成！（random.seed(42)，可复现）")
    print("=" * 60)
    print(f"  统一测试密码: {TEST_PASSWORD}")
    print(f"  核心账号（username=手机号）:")
    print(f"    PROSPECT  13810000001  意向客户")
    print(f"    STUDENT   13810000002  留学生")
    print(f"    EMPLOYEE  13810000003  员工")
    print(f"    MANAGER   13810000004  管理层")
    print(f"  其他账号: user000~user115（密码同上）")
    print("-" * 60)
    print(f"  用户: 120 (ADMIN/MANAGER/EMPLOYEE/STUDENT/PROSPECT)")
    print(f"  客户主表: 120, 待补全线索: 15")
    print(f"  CRM线索: 110, 研判: 150, 跟进: 123（含 3 条核心员工已到期跟进）")
    print(f"  FAQ: 105, 会话: 110, 消息: 200, 意图: 100, 推荐日志: 150")
    print(f"  活动: 20, 报名: 100, 课程: 15")
    print(f"  组织架构: 10, 日报: 120, 待办: 100, 成绩: 100")
    print(f"  学生服务: 100, 心理画像: 100, 心理预警: 100, 反馈工单: 100, 工单AI分析: ~80")
    print(f"  学业: 100, 申请进度: 100")
    print(f"  报告: 20, 报告附件: ~30")
    print(f"  系统事件: 100, 审批实例: 100, 审批任务: 100, 通知: 105（含核心账号 5 条）, 操作日志: 100")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
