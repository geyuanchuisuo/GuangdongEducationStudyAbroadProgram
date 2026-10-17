from datetime import date, timedelta

from app.core.exceptions import BusinessError, ConflictError, ForbiddenError, NotFoundError
from app.models.customer import Customer
from app.models.employee import EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.student import StudentScore
from app.models.system import ApprovalInstance
from app.models.user import User
from app.repositories.employee_repo import (
    DailyReportRepository,
    OrgRepository,
    ScoreRepository,
    TodoRepository,
)
from app.services.approval_engine import ApprovalBizType, ApprovalStatus, approval_engine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeService:
    """M3 员工模块业务逻辑。

    注意：
    - 日报唯一约束：(employee_id, report_date)，重复提交返回 40901
    - 代客申请：走 approval_engine.create(biz_type=convert)，经理审批
    - 数据隔离：普通员工只能看/操作自己的日报/待办；成绩按 student_id 查询不限员工
    """

    def __init__(
        self,
        db: AsyncSession,
        report_repo: DailyReportRepository,
        todo_repo: TodoRepository,
        org_repo: OrgRepository,
        score_repo: ScoreRepository,
    ):
        self.db = db
        self.report_repo = report_repo
        self.todo_repo = todo_repo
        self.org_repo = org_repo
        self.score_repo = score_repo

    # ── 日报 ──────────────────────────────────────────
    @staticmethod
    def _calc_is_late(report_date: date) -> bool:
        """迟报判定：report_date 为昨天（次日 0 点宽限内）也算迟报但免审批；今天不算。"""
        return report_date < date.today()

    async def submit_report(
        self, employee_id: int, report_date: date, content: str, status: str = "submitted"
    ) -> EmployeeDailyReport:
        if status not in ("draft", "submitted"):
            raise BusinessError(code=40002, message="status 仅支持 draft/submitted")
        if report_date > date.today():
            raise BusinessError(code=40002, message="日报日期不能晚于今天")
        # 超过宽限期（前天及更早）禁止直接正式提交，必须走补报审批
        if status == "submitted" and report_date < date.today() - timedelta(days=1):
            raise BusinessError(code=40002, message="已超过补提时限，请先存草稿再走补报申请")

        existing = await self.report_repo.get_by_emp_date(employee_id, report_date)
        if existing:
            if existing.status != "draft":
                raise ConflictError(message=f"{report_date} 日报已提交，请勿重复")
            # 草稿转正/更新草稿
            existing.content = content
            existing.status = status
            existing.is_late = self._calc_is_late(report_date) if status == "submitted" else False
            return await self.report_repo.update(existing)

        report = EmployeeDailyReport(
            employee_id=employee_id,
            report_date=report_date,
            content=content,
            status=status,
            is_late=self._calc_is_late(report_date) if status == "submitted" else False,
        )
        return await self.report_repo.create(report)

    async def update_draft(self, report_id: int, employee_id: int, content: str) -> EmployeeDailyReport:
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="日报不存在")
        if report.employee_id != employee_id:
            raise ForbiddenError(message="只能修改自己的日报")
        if report.status != "draft":
            raise BusinessError(code=40901, message="仅草稿状态可编辑")
        report.content = content
        return await self.report_repo.update(report)

    async def late_apply(self, report_id: int, employee_id: int, approver_id: int) -> dict:
        """日报补报申请：草稿 + 超过宽限期 → 走 approval late_report，经理审批。"""
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="日报不存在")
        if report.employee_id != employee_id:
            raise ForbiddenError(message="只能为自己的日报申请补报")
        if report.status != "draft":
            raise BusinessError(code=40901, message="仅草稿状态可申请补报")
        if report.report_date >= date.today() - timedelta(days=1):
            raise BusinessError(code=40002, message="该日期仍在补提宽限期内，可直接提交，无需审批")

        # 审批人必须是 MANAGER
        result = await self.db.execute(select(User).where(User.id == approver_id))
        approver = result.scalar_one_or_none()
        if not approver:
            raise NotFoundError(message="审批人不存在")
        if approver.user_type != "MANAGER":
            raise BusinessError(code=40002, message="审批人必须是管理层（MANAGER）")

        # 防止重复申请
        dup = await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.biz_type == ApprovalBizType.LATE_REPORT.value,
                ApprovalInstance.biz_id == report_id,
                ApprovalInstance.status == ApprovalStatus.PENDING.value,
            )
        )
        if dup.scalar_one_or_none():
            raise ConflictError(message="该日报已有待审批的补报申请")

        instance = await approval_engine.create(
            biz_type=ApprovalBizType.LATE_REPORT,
            initiator_id=employee_id,
            approver_id=approver_id,
            biz_id=report_id,
            title=f"日报补报申请：{report.report_date}",
        )
        report.status = "late_pending"
        await self.report_repo.update(report)
        return {
            "approval_id": instance.id,
            "biz_type": instance.biz_type,
            "biz_id": instance.biz_id,
            "status": instance.status,
        }

    async def late_review(self, approval_id: int, approver_id: int, action: str, comment: str | None) -> dict:
        """补报审批（MANAGER）：通过 → 日报转正（is_late=True）；驳回 → 退回草稿。"""
        if action not in ("approved", "rejected"):
            raise BusinessError(code=40002, message="action 仅支持 approved/rejected")
        instance = await approval_engine.get_by_id(approval_id)
        if not instance:
            raise NotFoundError(message="审批单不存在")
        if instance.biz_type != ApprovalBizType.LATE_REPORT.value:
            raise BusinessError(code=40002, message="该审批单不是日报补报类型")

        if action == "approved":
            instance = await approval_engine.approve(approval_id, approver_id, comment)
        else:
            instance = await approval_engine.reject(approval_id, approver_id, comment)

        report = await self.report_repo.get_by_id(instance.biz_id)
        if report:
            if action == "approved":
                report.status = "submitted"
                report.is_late = True
            else:
                report.status = "draft"
            await self.report_repo.update(report)
        return {"approval_id": instance.id, "status": instance.status}

    async def list_my_reports(self, employee_id: int, page: int, page_size: int) -> tuple[list[EmployeeDailyReport], int]:
        return await self.report_repo.list_by_employee(employee_id, page, page_size)

    async def list_all_reports(self, page: int, page_size: int) -> tuple[list[EmployeeDailyReport], int]:
        return await self.report_repo.list_all(page, page_size)

    async def reports_summary(self, start: date | None, end: date | None) -> list[tuple[date, int]]:
        return await self.report_repo.summary_by_date(start, end)

    # ── 待办 ──────────────────────────────────────────
    async def create_todo(self, employee_id: int, data: dict) -> EmployeeTodo:
        todo = EmployeeTodo(employee_id=employee_id, **data)
        return await self.todo_repo.create(todo)

    async def update_todo(self, todo_id: int, employee_id: int, data: dict) -> EmployeeTodo:
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise NotFoundError(message="待办不存在")
        if todo.employee_id != employee_id:
            raise ForbiddenError(message="只能操作自己的待办")
        return await self.todo_repo.update(todo, data)

    async def list_my_todos(
        self, employee_id: int, status: str | None, page: int, page_size: int
    ) -> tuple[list[EmployeeTodo], int]:
        return await self.todo_repo.list_by_employee(employee_id, status, page, page_size)

    # ── 组织架构 ──────────────────────────────────────
    async def get_org_tree(self) -> list[EmployeeOrg]:
        return await self.org_repo.list_all()

    # ── 成绩 ──────────────────────────────────────────
    async def record_score(self, data: dict) -> StudentScore:
        # 验证学生存在且身份为 STUDENT
        result = await self.db.execute(select(User).where(User.id == data["student_id"]))
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(message="学生不存在")
        if student.user_type != "STUDENT":
            raise BusinessError(code=40002, message=f"用户 {data['student_id']} 不是学生")
        score = StudentScore(**data)
        return await self.score_repo.create(score)

    async def list_scores(
        self, student_id: int | None, semester: str | None, page: int, page_size: int
    ) -> tuple[list[StudentScore], int]:
        return await self.score_repo.list_all(student_id, semester, page, page_size)

    # ── 代客申请留学生（approval convert） ─────────────
    async def apply_convert(
        self, employee_id: int, customer_id: int, approver_id: int, title: str | None
    ) -> dict:
        # 客户必须存在
        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError(message="客户不存在")

        # 审批人必须是 MANAGER
        result = await self.db.execute(select(User).where(User.id == approver_id))
        approver = result.scalar_one_or_none()
        if not approver:
            raise NotFoundError(message="审批人不存在")
        if approver.user_type != "MANAGER":
            raise BusinessError(code=40002, message="审批人必须是管理层（MANAGER）")

        final_title = title or f"代客申请：{customer.name or customer.phone} → 留学生"
        instance = await approval_engine.create(
            biz_type=ApprovalBizType.CONVERT,
            initiator_id=employee_id,
            approver_id=approver_id,
            biz_id=customer_id,
            title=final_title,
        )
        return {
            "approval_id": instance.id,
            "biz_type": instance.biz_type,
            "biz_id": instance.biz_id,
            "status": instance.status,
        }

    # ── 学生行政服务审批（请假/转班/复学等） ─────────────
    async def list_admin_services(
        self, employee_id: int, status: str | None, page: int, page_size: int
    ) -> tuple[list, int]:
        """员工查询自己作为 approver 的学生行政服务审批单（学生请假等）。"""
        from app.models.student import StudentAdminService
        stmt = select(StudentAdminService).where(StudentAdminService.approver_id == employee_id)
        count_stmt = select(StudentAdminService.id).where(StudentAdminService.approver_id == employee_id)
        if status:
            stmt = stmt.where(StudentAdminService.status == status)
            count_stmt = count_stmt.where(StudentAdminService.status == status)
        total = (await self.db.execute(count_stmt)).all()
        stmt = stmt.order_by(StudentAdminService.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), len(total)

    async def review_admin_service(
        self, service_id: int, employee_id: int, action: str, comment: str | None
    ) -> dict:
        """审批学生行政服务单。走 approval_engine.leave，同步更新 student_admin_service.status。"""
        from app.models.student import StudentAdminService
        result = await self.db.execute(
            select(StudentAdminService).where(StudentAdminService.id == service_id)
        )
        svc = result.scalar_one_or_none()
        if not svc:
            raise NotFoundError(message="审批单不存在")
        if svc.approver_id != employee_id:
            raise ForbiddenError(message="你不是该单的审批人")
        if svc.status != "待审批":
            raise ConflictError(message=f"该单已处理，当前状态：{svc.status}")

        if action not in ("approve", "reject"):
            raise BusinessError(code=40002, message="action 必须是 approve 或 reject")

        # 请假去重：同学生同时段已有待审批/已通过的请假记录
        if action == "approve" and svc.service_type == "请假":
            dup_result = await self.db.execute(
                select(StudentAdminService).where(
                    StudentAdminService.student_id == svc.student_id,
                    StudentAdminService.service_type == "请假",
                    StudentAdminService.id != svc.id,
                    StudentAdminService.status.in_(["待审批", "已通过"]),
                )
            )
            dup = dup_result.scalars().first()
            if dup:
                raise ConflictError(
                    message=f"该学生已有一条请假记录（id={dup.id}，状态={dup.status}），请先处理"
                )

        # 同步走 approval_engine，biz_id = service.id
        # 先找到对应的 approval_instance（如果学生端已发起），否则现场创建
        from app.models.system import ApprovalInstance
        inst_result = await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.biz_type == ApprovalBizType.LEAVE.value,
                ApprovalInstance.biz_id == service_id,
            )
        )
        instance = inst_result.scalar_one_or_none()
        if instance is None:
            # 学生端未走引擎，员工侧补建（initiator 用学生 id）
            instance = await approval_engine.create(
                biz_type=ApprovalBizType.LEAVE,
                initiator_id=svc.student_id,
                approver_id=employee_id,
                biz_id=service_id,
                title=f"学生{svc.student_id} {svc.service_type} 申请",
            )

        if action == "approve":
            instance = await approval_engine.approve(instance.id, employee_id, comment)
            svc.status = "已通过"
            from app.services.event_bus import event_bus
            from app.services.event_contracts import EventType
            await event_bus.publish(
                EventType.LEAVE_APPROVED,
                source_module="M3",
                payload={"student_id": svc.student_id, "leave_id": svc.id, "status": svc.status},
            )
        else:
            instance = await approval_engine.reject(instance.id, employee_id, comment)
            svc.status = "已拒绝"
            from app.services.event_bus import event_bus
            from app.services.event_contracts import EventType
            await event_bus.publish(
                EventType.LEAVE_REJECTED,
                source_module="M3",
                payload={"student_id": svc.student_id, "leave_id": svc.id, "status": svc.status},
            )

        await self.db.commit()
        return {
            "service_id": svc.id,
            "status": svc.status,
            "approval_id": instance.id,
            "approval_status": instance.status,
        }

    # ── 口述日报（AI 整理） ──────────────────────────────
    async def generate_oral_report(
        self, employee_id: int, raw_text: str, report_date: date | None, save: bool = False
    ) -> dict:
        """调 AI 网关把口述文本整理成结构化日报。

        save=True 时同时落库到 employee_daily_report（沿用唯一约束）。
        """
        from datetime import date as _date
        from app.services.ai_service import AgentType, ai_service

        target_date = report_date or _date.today()
        prompt = (
            "请将以下员工口述内容整理为结构化工作日报，"
            "包含三个部分：一、今日完成事项（按条列出）；二、遇到的问题；三、明日计划。"
            "保持简洁专业，不添加未提及的内容。\n\n"
            f"口述原文：{raw_text}"
        )
        try:
            resp = await ai_service.chat(
                agent=AgentType.EMPLOYEE,
                message=prompt,
                session_id="new",
                user_id=f"employee_{employee_id}",
            )
            structured = resp.content
            session_id = resp.session_id
        except Exception as exc:
            raise BusinessError(code=50002, message=f"AI 整理失败：{exc}") from exc

        saved_id = None
        if save:
            # 统一走 submit_report：唯一约束 + 迟报/草稿规则一致
            report = await self.submit_report(employee_id, target_date, structured)
            saved_id = report.id

        return {
            "raw_text": raw_text,
            "structured": structured,
            "report_date": target_date,
            "session_id": session_id,
            "saved_report_id": saved_id,
        }

    # ── CRM 客户录入（多格式 + AI 研判） ─────────────────
    async def create_crm_lead(self, employee_id: int, data: dict) -> dict:
        """员工录入线索：
        1. 按 phone 查/建 customer（先录入者获跟进权，已存在则不抢）
        2. 落 crm_lead（owner=当前员工）
        3. auto_assess=True 时调 AI 网关做客户研判，写 customer_assessment
        """
        import json
        from app.models.crm import CrmLead, CustomerAssessment

        phone = (data.get("phone") or "").strip() or None
        customer = None
        customer_existed = False

        if phone:
            result = await self.db.execute(select(Customer).where(Customer.phone == phone))
            customer = result.scalar_one_or_none()
            if customer:
                customer_existed = True
                # 已存在客户：不抢 owner，但补全缺省字段
                if not customer.owner_employee_id:
                    customer.owner_employee_id = employee_id

        if customer is None:
            customer = Customer(
                phone=phone,
                wechat=data.get("wechat"),
                name=data.get("name"),
                gender=data.get("gender"),
                age=data.get("age"),
                education=data.get("education"),
                source_channel=data.get("source_channel"),
                owner_employee_id=employee_id,
                status="NEW",
            )
            self.db.add(customer)
            await self.db.flush()

        # 落 lead
        raw_input_parts = []
        if data.get("raw_text"):
            raw_input_parts.append(data["raw_text"])
        if data.get("file_urls"):
            raw_input_parts.append(f"附件 {len(data['file_urls'])} 个：{'; '.join(data['file_urls'])}")
        raw_input = "\n".join(raw_input_parts) or "无内容"

        lead = CrmLead(
            customer_id=customer.id,
            source=data.get("source_channel") or "employee",
            raw_input=raw_input,
            background_info=data.get("background_info"),
            owner_employee_id=employee_id,
            status="new",
        )
        self.db.add(lead)
        await self.db.flush()

        # AI 研判（可选）
        assessment_id = None
        assessment_status = "skipped"
        if data.get("auto_assess", True):
            if not phone:
                assessment_status = "invalid_phone"
            else:
                try:
                    from app.services.ai_service import AgentType, ai_service
                    prompt = (
                        "请基于以下客户原始信息，输出客户研判报告（JSON 格式）："
                        "包含 overview（客户速览）、score（匹配度评分 90/70/50/20 之一）、"
                        "follow_up_advice（跟进建议）、recommended_programs（推荐项目列表）。\n\n"
                        f"客户信息：\n姓名：{data.get('name') or '未知'}\n"
                        f"手机：{phone}\n学历：{data.get('education') or '未知'}\n"
                        f"年龄：{data.get('age') or '未知'}\n"
                        f"背景：{data.get('background_info') or '无'}\n"
                        f"原始录入：{data.get('raw_text') or '无'}"
                    )
                    ai_resp = await ai_service.chat(
                        agent=AgentType.EMPLOYEE,
                        message=prompt,
                        session_id="new",
                        user_id=f"employee_{employee_id}",
                    )
                    content = ai_resp.content or ""
                    overview = ""
                    score = None
                    follow_up_advice = ""
                    # 尝试解析 JSON；失败则塞原文
                    try:
                        start = content.find("{")
                        end = content.rfind("}")
                        if start >= 0 and end > start:
                            parsed = json.loads(content[start:end + 1])
                            overview = parsed.get("overview", "")
                            score = parsed.get("score")
                            follow_up_advice = parsed.get("follow_up_advice", "")
                        else:
                            overview = content[:500]
                    except Exception:
                        overview = content[:500]

                    assessment = CustomerAssessment(
                        customer_id=customer.id,
                        input_source="employee",
                        status="valid",
                        overview=overview,
                        score=score if isinstance(score, int) else None,
                        follow_up_advice=follow_up_advice or content[:500],
                        employee_id=employee_id,
                        prompt_version="v1",
                        dify_run_id=ai_resp.session_id,
                    )
                    self.db.add(assessment)
                    await self.db.flush()
                    assessment_id = assessment.id
                    assessment_status = "valid"
                except Exception as exc:
                    assessment_status = f"failed: {exc}"
        else:
            if not phone:
                assessment_status = "invalid_phone"

        await self.db.commit()

        message = "录入成功"
        if customer_existed:
            message = "客户已存在，已关联并保留原跟进员工"
        if assessment_status.startswith("failed"):
            message += f"；研判失败：{assessment_status}"
        elif assessment_status == "invalid_phone":
            message += "；无手机号，未做 AI 研判"

        return {
            "lead_id": lead.id,
            "customer_id": customer.id,
            "customer_existed": customer_existed,
            "assessment_id": assessment_id,
            "status": assessment_status,
            "message": message,
        }

    async def create_follow_up(self, employee_id: int, data: dict) -> "object":
        """新增跟进记录。"""
        from app.models.crm import CrmFollowUp
        # 客户必须存在
        result = await self.db.execute(select(Customer).where(Customer.id == data["customer_id"]))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError(message="客户不存在")

        follow = CrmFollowUp(employee_id=employee_id, **data)
        self.db.add(follow)
        await self.db.commit()
        await self.db.refresh(follow)
        return follow

    async def list_my_follow_ups(
        self, employee_id: int, customer_id: int | None, page: int, page_size: int
    ) -> tuple[list, int]:
        """员工查询自己的跟进记录。"""
        from app.models.crm import CrmFollowUp
        stmt = select(CrmFollowUp).where(CrmFollowUp.employee_id == employee_id)
        count_stmt = select(CrmFollowUp.id).where(CrmFollowUp.employee_id == employee_id)
        if customer_id:
            stmt = stmt.where(CrmFollowUp.customer_id == customer_id)
            count_stmt = count_stmt.where(CrmFollowUp.customer_id == customer_id)
        total = len((await self.db.execute(count_stmt)).all())
        stmt = stmt.order_by(CrmFollowUp.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # ── 指令式业务处理（AI 解析 + 二次确认） ─────────────
    # token 存内存 dict：{token: {employee_id, action, expire_at}}，10 分钟过期
    _PENDING_COMMANDS: dict = {}

    async def parse_command(self, employee_id: int, text: str) -> dict:
        """调 AI 解析自然语言指令为结构化动作。返回 token + action。"""
        import json
        import secrets
        import time
        from app.services.ai_service import AgentType, ai_service

        prompt = (
            "请把员工的自然语言指令解析为一个 JSON 动作对象，只输出 JSON，不要任何解释。\n"
            "支持的动作类型 action_type：\n"
            "  - follow_up.create（新增跟进记录，params: customer_id 必填、content 必填、follow_type/next_action/next_date 可选）\n"
            "  - todo.create（新增待办，params: title 必填、description/due_time/priority 可选）\n"
            "  - score.record（录入成绩，params: student_id 必填、course_name 必填、score 必填、semester 可选）\n"
            "  - report.submit（提交日报，params: report_date 必填 YYYY-MM-DD、content 必填）\n"
            "  - unknown（无法识别，params: {reason: \"...\"}）\n"
            "输出格式：{\"action_type\": \"...\", \"params\": {...}, \"summary\": \"一句话描述将执行的动作\"}\n\n"
            f"员工指令：{text}"
        )
        try:
            resp = await ai_service.chat(
                agent=AgentType.EMPLOYEE,
                message=prompt,
                session_id="new",
                user_id=f"employee_{employee_id}",
            )
        except Exception as exc:
            raise BusinessError(code=50002, message=f"AI 解析失败：{exc}") from exc

        content = (resp.content or "").strip()
        try:
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("no json")
            parsed = json.loads(content[start:end + 1])
        except Exception:
            raise BusinessError(code=40002, message="AI 未返回有效 JSON，请换个说法") from None

        action_type = parsed.get("action_type") or "unknown"
        params = parsed.get("params") or {}
        summary = parsed.get("summary") or text
        if action_type == "unknown":
            raise BusinessError(code=40002, message=f"无法识别指令：{params.get('reason', '请换个说法')}")

        token = secrets.token_urlsafe(24)
        expire_at = time.time() + 600
        # 清理过期 token
        for k in [k for k, v in EmployeeService._PENDING_COMMANDS.items() if v["expire_at"] < time.time()]:
            EmployeeService._PENDING_COMMANDS.pop(k, None)
        EmployeeService._PENDING_COMMANDS[token] = {
            "employee_id": employee_id,
            "action_type": action_type,
            "params": params,
            "summary": summary,
            "expire_at": expire_at,
        }
        return {
            "token": token,
            "action": {"action_type": action_type, "params": params, "summary": summary},
            "expires_in": 600,
        }

    async def execute_command(self, employee_id: int, token: str, confirm: bool) -> dict:
        """二次确认后执行动作。"""
        import time

        pending = EmployeeService._PENDING_COMMANDS.pop(token, None)
        if not pending:
            raise NotFoundError(message="token 无效或已过期")
        if pending["employee_id"] != employee_id:
            raise ForbiddenError(message="只能执行自己的指令")
        if pending["expire_at"] < time.time():
            raise ConflictError(message="token 已过期，请重新解析")

        if not confirm:
            return {"executed": False, "result": None, "message": "已取消"}

        action_type = pending["action_type"]
        params = pending["params"]
        result: dict = {}

        if action_type == "follow_up.create":
            follow = await self.create_follow_up(employee_id, params)
            result = {"follow_up_id": follow.id}
        elif action_type == "todo.create":
            todo = await self.create_todo(employee_id, params)
            result = {"todo_id": todo.id}
        elif action_type == "score.record":
            score = await self.record_score(params)
            result = {"score_id": score.id}
        elif action_type == "report.submit":
            from datetime import date as _date, datetime as _dt
            rd = params.get("report_date")
            if isinstance(rd, str):
                rd = _dt.strptime(rd, "%Y-%m-%d").date()
            report = await self.submit_report(employee_id, rd or _date.today(), params["content"])
            result = {"report_id": report.id}
        else:
            raise BusinessError(code=40002, message=f"暂不支持的动作类型：{action_type}")

        return {"executed": True, "result": result, "message": "已执行"}

    # ── 客户状态机（6 态流转） ──────────────────────────
    CUSTOMER_STATES = {"新录入", "跟进中", "意向强烈", "已签约", "已入学", "已流失"}
    CUSTOMER_TRANSITIONS: dict[str, list[str]] = {
        "新录入": ["跟进中", "已流失"],
        "跟进中": ["意向强烈", "已流失"],
        "意向强烈": ["已签约", "已流失"],
        "已签约": ["已入学", "已流失"],
        "已入学": ["已流失"],
        "已流失": ["跟进中"],
    }

    async def update_customer_status(
        self, employee_id: int, customer_id: int, new_status: str, reason: str | None
    ) -> dict:
        """更新客户状态，校验状态机约束，写操作日志。"""
        if new_status not in self.CUSTOMER_STATES:
            raise BusinessError(code=40002, message=f"无效状态：{new_status}，可选：{self.CUSTOMER_STATES}")

        result = await self.db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError(message="客户不存在")

        old_status = customer.status
        # 兼容旧数据英文状态
        old_status_cn = {"NEW": "新录入", "FOLLOWING": "跟进中", "CONVERTED": "已签约"}.get(old_status, old_status)
        allowed = self.CUSTOMER_TRANSITIONS.get(old_status_cn, [])
        if new_status not in allowed:
            raise ConflictError(
                message=f"不能从「{old_status_cn}」流转到「{new_status}」，允许：{allowed}"
            )

        customer.status = new_status
        # 写操作日志
        from app.models.system import SysOperationLog
        log = SysOperationLog(
            user_id=employee_id,
            module="M3",
            action="customer_status_change",
            target_type="customer",
            target_id=customer_id,
            detail={"old_status": old_status_cn, "new_status": new_status, "reason": reason},
        )
        self.db.add(log)
        await self.db.commit()
        return {
            "customer_id": customer_id,
            "old_status": old_status_cn,
            "new_status": new_status,
            "changed_at": customer.updated_at,
        }

    # ── 意向客户查询（数据隔离 + 筛选排序） ───────────────
    async def list_my_customers(
        self,
        employee_id: int,
        status: str | None,
        source_channel: str | None,
        score_min: int | None,
        sort_by: str,
        page: int,
        page_size: int,
    ) -> tuple[list, int]:
        """员工查询自己名下客户，支持筛选排序。MANAGER 传 employee_id=None 查全部。"""
        from app.models.crm import CrmFollowUp, CustomerAssessment

        stmt = select(Customer)
        count_stmt = select(func.count()).select_from(Customer)
        if employee_id is not None:
            stmt = stmt.where(Customer.owner_employee_id == employee_id)
            count_stmt = count_stmt.where(Customer.owner_employee_id == employee_id)
        if status:
            stmt = stmt.where(Customer.status == status)
            count_stmt = count_stmt.where(Customer.status == status)
        if source_channel:
            stmt = stmt.where(Customer.source_channel == source_channel)
            count_stmt = count_stmt.where(Customer.source_channel == source_channel)

        # 按匹配度筛选：join 最新 assessment
        if score_min is not None:
            latest_score = (
                select(
                    CustomerAssessment.customer_id,
                    func.max(CustomerAssessment.score).label("max_score"),
                )
                .group_by(CustomerAssessment.customer_id)
                .subquery()
            )
            stmt = stmt.join(latest_score, Customer.id == latest_score.c.customer_id).where(
                latest_score.c.max_score >= score_min
            )

        total = (await self.db.execute(count_stmt)).scalar_one()

        # 排序
        if sort_by == "updated_at":
            stmt = stmt.order_by(Customer.updated_at.desc())
        elif sort_by == "score":
            latest_score = (
                select(
                    CustomerAssessment.customer_id,
                    func.max(CustomerAssessment.score).label("max_score"),
                )
                .group_by(CustomerAssessment.customer_id)
                .subquery()
            )
            stmt = stmt.outerjoin(latest_score, Customer.id == latest_score.c.customer_id).order_by(
                latest_score.c.max_score.is_(None),
                latest_score.c.max_score.desc(),
            )
        else:
            stmt = stmt.order_by(Customer.created_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())

        # 补充 last_follow_at 和 assessment_score
        items = []
        for c in customers:
            # 最新跟进时间
            follow_result = await self.db.execute(
                select(func.max(CrmFollowUp.created_at)).where(CrmFollowUp.customer_id == c.id)
            )
            last_follow = follow_result.scalar_one_or_none()
            # 最新研判分
            score_result = await self.db.execute(
                select(func.max(CustomerAssessment.score)).where(CustomerAssessment.customer_id == c.id)
            )
            score = score_result.scalar_one_or_none()
            items.append({
                "id": c.id,
                "phone": c.phone,
                "wechat": c.wechat,
                "name": c.name,
                "gender": c.gender,
                "age": c.age,
                "education": c.education,
                "source_channel": c.source_channel,
                "status": c.status,
                "owner_employee_id": c.owner_employee_id,
                "last_follow_at": last_follow,
                "assessment_score": score,
                "created_at": c.created_at,
            })
        return items, total

    # ── 投诉工单处理 ──────────────────────────────────
    async def list_tickets(self, employee_id: int, status: str | None, page: int, page_size: int) -> tuple[list, int]:
        """员工查看名下学生的投诉工单。"""
        from app.models.student import StudentFeedbackTicket
        stmt = select(StudentFeedbackTicket)
        count_stmt = select(func.count()).select_from(StudentFeedbackTicket)
        if status:
            stmt = stmt.where(StudentFeedbackTicket.status == status)
            count_stmt = count_stmt.where(StudentFeedbackTicket.status == status)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(StudentFeedbackTicket.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def handle_ticket(self, employee_id: int, ticket_id: int, solution: str) -> dict:
        """处理投诉工单，写解决方案，发事件。"""
        from app.models.student import StudentFeedbackTicket
        result = await self.db.execute(
            select(StudentFeedbackTicket).where(StudentFeedbackTicket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(message="工单不存在")
        ticket.status = "已处理"
        ticket.solution = solution
        await self.db.commit()
        # 发事件
        try:
            await self.event_bus.publish(
                event_type="complaint.resolved",
                source_module="M3",
                payload={"ticket_id": ticket.id, "student_id": ticket.student_id, "handler_id": employee_id},
            )
        except Exception:
            pass
        return {"ticket_id": ticket.id, "status": "已处理"}

    # ── 心理关怀待办标记 ───────────────────────────────
    VALID_PSYCH_ACTIONS = {"communicated", "referred", "resolved"}

    async def handle_psych_alert(self, employee_id: int, alert_id: int, action: str, note: str | None) -> dict:
        """标记心理预警处理动作，形成关怀记录。"""
        from app.models.student import StudentPsychAlert
        from datetime import datetime, timezone
        if action not in self.VALID_PSYCH_ACTIONS:
            raise BusinessError(code=40002, message=f"无效动作：{action}，可选：{self.VALID_PSYCH_ACTIONS}")
        result = await self.db.execute(
            select(StudentPsychAlert).where(StudentPsychAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise NotFoundError(message="预警不存在")
        alert.handled_action = action
        alert.handled_at = datetime.now(timezone.utc)
        alert.teacher_id = employee_id
        alert.status = "已处理"
        await self.db.commit()
        return {"alert_id": alert.id, "action": action, "status": "已处理"}
