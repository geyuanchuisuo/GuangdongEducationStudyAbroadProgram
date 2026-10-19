import json
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

from app.core.exceptions import BusinessError, ConflictError, ForbiddenError, NotFoundError
from app.models.course import CourseProject
from app.models.customer import Customer
from app.models.employee import DailyReportAnnotation, EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.student import StudentPsychAlert, StudentScore
from app.models.system import ApprovalInstance
from app.models.user import User
from app.repositories.employee_repo import (
    DailyReportRepository,
    OrgRepository,
    ScoreRepository,
    TodoRepository,
)
from app.services.approval_engine import ApprovalBizType, ApprovalStatus, approval_engine
from app.utils.logger import logger  # 合并修复：model 回落分支引用了 logger，此前未导入会 NameError→50001
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
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
    @staticmethod
    def _norm_semester(value: str | None) -> str:
        # semester 一律规范化为空串（不用 NULL），确保 uq_student_score_unique 唯一索引在 MySQL 下生效
        return (value or "").strip()

    async def record_score(self, data: dict) -> StudentScore:
        # 验证学生存在且身份为 STUDENT
        result = await self.db.execute(select(User).where(User.id == data["student_id"]))
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(message="学生不存在")
        if student.user_type != "STUDENT":
            raise BusinessError(code=40002, message=f"用户 {data['student_id']} 不是学生")
        data["semester"] = self._norm_semester(data.get("semester"))
        # 服务层查重（唯一键 student_id+course_name+semester），冲突返回 40901
        dup = await self.db.execute(
            select(StudentScore).where(
                StudentScore.student_id == data["student_id"],
                StudentScore.course_name == data["course_name"],
                StudentScore.semester == data["semester"],
            )
        )
        if dup.scalar_one_or_none():
            raise ConflictError(message="该学生在此学期已录入该课程成绩，请直接修改")
        score = StudentScore(**data)
        try:
            return await self.score_repo.create(score)
        except IntegrityError:
            # 并发兜底：服务层查重后另一请求抢先插入，数据库唯一索引拦截
            await self.db.rollback()
            raise ConflictError(message="该学生在此学期已录入该课程成绩，请直接修改")

    async def update_score(self, score_id: int, data: dict) -> StudentScore:
        result = await self.db.execute(select(StudentScore).where(StudentScore.id == score_id))
        score = result.scalar_one_or_none()
        if not score:
            raise NotFoundError(message="成绩记录不存在")
        score.score = data["score"]
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError(message="修改后与已有成绩记录冲突")
        await self.db.refresh(score)
        return score

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

        # v6.11.32：仅意向客户（NEW/FOLLOWING/STRONG）可发起留学生转化，
        # 防止绕过前端对已签约/已入学/已流失客户重复提单（口径同 report_calculator.INTENT_STATUSES）
        if customer.status not in ("NEW", "FOLLOWING", "STRONG"):
            raise BusinessError(
                code=40003,
                message=f"该客户当前状态为「{customer.status}」，仅意向客户可发起留学生转化申请",
            )

        # 审批人必须是 MANAGER
        result = await self.db.execute(select(User).where(User.id == approver_id))
        approver = result.scalar_one_or_none()
        if not approver:
            raise NotFoundError(message="审批人不存在")
        if approver.user_type != "MANAGER":
            raise BusinessError(code=40002, message="审批人必须是管理层（MANAGER）")

        existing = (await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.biz_type == ApprovalBizType.CONVERT.value,
                ApprovalInstance.biz_id == customer_id,
                ApprovalInstance.status == ApprovalStatus.PENDING.value,
            ).limit(1)
        )).scalars().first()
        if existing:
            raise ConflictError(message="该客户已有待审批的留学生转化申请")
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
        if svc.approver_id is not None and svc.approver_id != employee_id:
            raise ForbiddenError(message="你不是该单的审批人")
        # approver_id 为空（学生端未关联到负责员工）时，任何员工/管理层可兜底认领审批
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

    async def delete_follow_up(self, employee_id: int, follow_id: int) -> None:
        """删除跟进记录（数据隔离：只能删自己的；MANAGER 可删任意）。v6.11.23"""
        from app.models.crm import CrmFollowUp
        result = await self.db.execute(select(CrmFollowUp).where(CrmFollowUp.id == follow_id))
        follow = result.scalar_one_or_none()
        if not follow:
            raise NotFoundError(message="跟进记录不存在")
        user = await self.db.get(User, employee_id)
        if user is not None and user.user_type != "MANAGER" and follow.employee_id != employee_id:
            raise NotFoundError(message="跟进记录不存在")
        await self.db.delete(follow)
        await self.db.commit()

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

    _COMMAND_LOCAL_HINT = (
        "本地兜底解析句式示例："
        "「给客户12添加跟进记录：明天上午电话回访」/"
        "「新增待办：周五前回访客户」/"
        "「录入学生3成绩：数据库 92分」/"
        "「提交日报：今日完成客户回访3次」"
    )

    @staticmethod
    def _local_parse_command(text: str) -> dict:
        """AI 不可用/返回无效时的本地规则兜底解析（关键词+正则）。

        返回与 AI 相同结构的动作 dict；无法识别返回 unknown（reason 带句式提示），
        由调用方统一按 40002 处理。识别精度有限，仅覆盖常见指令句式。"""
        import re
        from datetime import date as _d, timedelta as _td

        t = (text or "").strip()

        def after_colon(s: str) -> str | None:
            m = re.search(r"[：:]", s)
            tail = s[m.end():].strip() if m else ""
            return tail or None

        def iso_date(s: str) -> str | None:
            m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", s)
            return m.group(1) if m else None

        def unknown(reason: str) -> dict:
            return {"action_type": "unknown", "params": {"reason": reason},
                    "summary": "无法识别指令"}

        # 1) 日报：「提交日报：内容」
        if "日报" in t:
            rd = iso_date(t) or _d.today().isoformat()
            content = after_colon(t) or t
            return {"action_type": "report.submit",
                    "params": {"report_date": rd, "content": content},
                    "summary": f"提交日报（{rd}）"}

        # 2) 成绩：「录入学生3成绩：数据库 92分」
        if "成绩" in t:
            m_stu = re.search(r"学生\s*(\d+)", t)
            m_score = re.search(r"(\d+(?:\.\d{1,2})?)\s*分", t)
            body = after_colon(t)
            course = None
            if body:
                course = re.sub(r"\d+(?:\.\d{1,2})?\s*分.*$", "", body).strip() or None
            if course is None:
                m_c = re.search(r"课程\s*([\u4e00-\u9fa5A-Za-z0-9]+)", t)
                course = m_c.group(1) if m_c else None
            if not (m_stu and m_score and course):
                return unknown("未能提取学生编号/课程/分数，请按「录入学生3成绩：数据库 92分」格式")
            return {"action_type": "score.record",
                    "params": {"student_id": int(m_stu.group(1)),
                               "course_name": course,
                               "score": float(m_score.group(1))},
                    "summary": f"录入学生{m_stu.group(1)}「{course}」成绩 {m_score.group(1)} 分"}

        # 3) 跟进：「给客户12添加跟进记录：明天上午电话回访」
        if "跟进" in t:
            m_cust = re.search(r"客户\s*(\d+)", t)
            content = after_colon(t) or t
            if not m_cust:
                return unknown("需要客户编号，请按「给客户12添加跟进记录：明天回访」格式")
            return {"action_type": "follow_up.create",
                    "params": {"customer_id": int(m_cust.group(1)), "content": content},
                    "summary": f"为客户{m_cust.group(1)}新增跟进记录"}

        # 4) 待办：「新增待办：xxx」/「提醒我 xxx」
        if "待办" in t or "提醒我" in t:
            title = after_colon(t) or re.sub(
                r"^(帮我)?(新增|创建|添加)?(一个)?(待办|提醒我)[，,：:]?", "", t).strip()
            if not title:
                return unknown("未能提取待办标题，请按「新增待办：周五前回访客户」格式")
            params: dict = {"title": title}
            due = iso_date(t)
            if not due:
                today = _d.today()
                due = (today + _td(days=1)).isoformat() if "明天" in t else \
                      ((today + _td(days=2)).isoformat() if "后天" in t else None)
            if due:
                params["due_time"] = due
            return {"action_type": "todo.create", "params": params,
                    "summary": f"新增待办「{title}」"}

        return unknown(f"无法识别该指令。{EmployeeService._COMMAND_LOCAL_HINT}")

    async def parse_command(self, employee_id: int, text: str) -> dict:
        """解析自然语言指令为结构化动作：AI 优先，AI 失败/无效返回时自动本地规则兜底。

        返回 token + action（action.source 标记解析来源：ai=Dify / local=本地兜底）。"""
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
            source = "ai"
        except Exception:
            resp = None
            source = "local"

        if resp is not None:
            content = (resp.content or "").strip()
            try:
                start = content.find("{")
                end = content.rfind("}")
                if start < 0 or end <= start:
                    raise ValueError("no json")
                parsed = json.loads(content[start:end + 1])
            except Exception:
                parsed = self._local_parse_command(text)
                source = "local"
        else:
            parsed = self._local_parse_command(text)

        action_type = parsed.get("action_type") or "unknown"
        params = parsed.get("params") or {}
        summary = parsed.get("summary") or text
        if action_type == "unknown":
            reason = params.get("reason", "请换个说法")
            if source == "local":
                raise BusinessError(code=40002,
                                    message=f"AI 不可用且本地兜底无法识别指令：{reason}")
            raise BusinessError(code=40002, message=f"无法识别指令：{reason}")

        if source == "local":
            summary = f"【本地兜底】{summary}"

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
            "action": {"action_type": action_type, "params": params,
                       "summary": summary, "source": source},
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
        # commit 后对象属性已过期（expired），必须 refresh 再读，否则异步上下文触发 MissingGreenlet
        await self.db.refresh(customer)
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
        last_follow_start: date | None = None,
        last_follow_end: date | None = None,
        keyword: str | None = None,
    ) -> tuple[list, int]:
        """员工查询自己名下客户，支持筛选排序。MANAGER 传 employee_id=None 查全部（v6.6.0 支持按员工下钻）。

        v6.11.32：新增 keyword，按姓名/手机号在库内模糊匹配（服务端过滤），
        解决前端只在已加载分页里做本地关键字过滤导致「搜索命中不到后面页的客户」。
        """
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
        # v6.11.32：关键字服务端模糊匹配（姓名 / 手机号），避免只过滤前端已加载的一页
        if keyword:
            kw = f"%{keyword.strip()}%"
            cond = or_(Customer.name.like(kw), Customer.phone.like(kw))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

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

        # 按最后跟进时间筛选（v6.6.0）：last_follow_at ∈ [start, end]，仅命中已有跟进的客户
        if last_follow_start is not None or last_follow_end is not None:
            last_follow_sq = (
                select(
                    CrmFollowUp.customer_id,
                    func.max(CrmFollowUp.created_at).label("last_follow"),
                )
                .group_by(CrmFollowUp.customer_id)
                .subquery()
            )
            stmt = stmt.join(last_follow_sq, Customer.id == last_follow_sq.c.customer_id)
            count_stmt = count_stmt.join(last_follow_sq, Customer.id == last_follow_sq.c.customer_id)
            if last_follow_start is not None:
                stmt = stmt.where(last_follow_sq.c.last_follow >= last_follow_start)
                count_stmt = count_stmt.where(last_follow_sq.c.last_follow >= last_follow_start)
            if last_follow_end is not None:
                stmt = stmt.where(last_follow_sq.c.last_follow < last_follow_end + timedelta(days=1))
                count_stmt = count_stmt.where(last_follow_sq.c.last_follow < last_follow_end + timedelta(days=1))

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
            # 最新研判的推荐产品（v6.6.0：对齐需求"查看研判结果（匹配度评分、推荐产品）"）
            rec_result = await self.db.execute(
                select(CustomerAssessment.recommended_json)
                .where(CustomerAssessment.customer_id == c.id)
                .order_by(CustomerAssessment.created_at.desc())
                .limit(1)
            )
            recommended = rec_result.scalar_one_or_none()
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
                "recommended": recommended,
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

    async def list_psych_alerts(self, current_user: User, status: str | None, page: int, page_size: int):
        """心理预警列表（v6.11.35）：EMPLOYEE 仅负责学生的预警，MANAGER 全量。"""
        q = select(StudentPsychAlert, User.real_name).join(User, User.id == StudentPsychAlert.student_id)
        if status:
            q = q.where(StudentPsychAlert.status == status)
        if current_user.user_type != "MANAGER":
            owned = select(Customer.sys_user_id).where(Customer.owner_employee_id == current_user.id)
            q = q.where(StudentPsychAlert.student_id.in_(owned))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = (
            await self.db.execute(
                q.order_by(StudentPsychAlert.create_time.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        items = [
            {
                "id": alert.id,
                "student_id": alert.student_id,
                "student_name": student_name,
                "trigger_reason": alert.trigger_reason,
                "risk_level": alert.risk_level,
                "status": alert.status,
                "handled_action": alert.handled_action,
                "handled_at": alert.handled_at,
                "create_time": alert.create_time,
            }
            for alert, student_name in rows
        ]
        return items, total

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

    # ── 日报批示（MANAGER） ───────────────────────────
    async def annotate_report(self, report_id: int, manager_id: int, content: str) -> DailyReportAnnotation:
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="日报不存在")
        annotation = DailyReportAnnotation(report_id=report_id, manager_id=manager_id, content=content)
        self.db.add(annotation)
        await self.db.commit()
        await self.db.refresh(annotation)
        return annotation

    async def list_annotations(self, report_id: int, user: User) -> list[DailyReportAnnotation]:
        """仅日报所属员工本人 + MANAGER 可见。"""
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(message="日报不存在")
        if user.user_type != "MANAGER" and report.employee_id != user.id:
            raise ForbiddenError(message="无权限查看该日报批示")
        result = await self.db.execute(
            select(DailyReportAnnotation)
            .where(DailyReportAnnotation.report_id == report_id)
            .order_by(DailyReportAnnotation.create_time)
        )
        return list(result.scalars().all())

    # ── 客户再分配（MANAGER 直接生效 + 操作日志 + 事件） ──
    async def reassign_customers(
        self, manager_id: int, from_employee_id: int, to_employee_id: int, customer_ids: list[int] | None
    ) -> dict:
        if from_employee_id == to_employee_id:
            raise BusinessError(code=40002, message="原归属与新归属不能相同")
        for uid, label in ((from_employee_id, "原归属员工"), (to_employee_id, "新归属员工")):
            result = await self.db.execute(select(User).where(User.id == uid))
            u = result.scalar_one_or_none()
            if not u:
                raise NotFoundError(message=f"{label}不存在")
            if u.user_type not in ("EMPLOYEE", "MANAGER"):
                raise BusinessError(code=40002, message=f"{label}必须是员工或管理层")

        stmt = select(Customer).where(Customer.owner_employee_id == from_employee_id)
        if customer_ids:
            stmt = stmt.where(Customer.id.in_(customer_ids))
        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())
        if not customers:
            raise NotFoundError(message="没有可转移的客户")
        moved_ids = [c.id for c in customers]
        for c in customers:
            c.owner_employee_id = to_employee_id

        from app.models.system import SysOperationLog
        self.db.add(SysOperationLog(
            user_id=manager_id,
            module="M3",
            action="customer_reassign",
            target_type="customer",
            target_id=None,
            detail={"from": from_employee_id, "to": to_employee_id, "customer_ids": moved_ids},
        ))
        await self.db.commit()

        from app.services.event_bus import event_bus
        from app.services.event_contracts import EventType
        await event_bus.publish(
            EventType.LEAD_TRANSFERRED,
            source_module="M3",
            payload={
                "from_employee_id": from_employee_id,
                "to_employee_id": to_employee_id,
                "customer_ids": moved_ids,
                "operator_id": manager_id,
            },
        )
        return {"moved": len(moved_ids), "customer_ids": moved_ids}

    # ── 个人信息 ──────────────────────────────────────
    async def update_profile(self, user_id: int, data: dict) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(message="用户不存在")
        # 手机号唯一校验
        new_phone = data.get("phone")
        if new_phone and new_phone != user.phone:
            dup = await self.db.execute(select(User).where(User.phone == new_phone))
            if dup.scalar_one_or_none():
                raise ConflictError(message="该手机号已被其他账号使用")
        for k, v in data.items():
            setattr(user, k, v)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        from app.core.security import hash_password, verify_password
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError(message="用户不存在")
        if not verify_password(old_password, user.password_hash):
            raise BusinessError(code=40001, message="旧密码不正确")
        user.password_hash = hash_password(new_password)
        await self.db.commit()

    async def profile_stats(self, user_id: int) -> dict:
        from sqlalchemy import func
        month_start = date.today().replace(day=1)
        base = select(func.count()).select_from(Customer).where(Customer.owner_employee_id == user_id)
        total = (await self.db.execute(base)).scalar_one()
        month_new = (await self.db.execute(
            base.where(Customer.created_at >= month_start)
        )).scalar_one()
        rows = (await self.db.execute(
            select(Customer.status, func.count()).where(Customer.owner_employee_id == user_id).group_by(Customer.status)
        )).all()
        by_status = {s: c for s, c in rows}

        def _count(*keys: str) -> int:
            return sum(by_status.get(k, 0) for k in keys)

        return {
            "total": total,
            "month_new": month_new,
            # 兼容中文 6 态与历史英文编码
            "following": _count("跟进中", "新录入", "意向强烈", "NEW", "FOLLOWING"),
            "signed": _count("已签约", "已入学", "CONVERTED"),
            "lost": _count("已流失", "CHURNED"),
        }

    # ── CSV 导出（同步，BOM 头兼容 Excel 中文） ────────
    @staticmethod
    def _to_csv(header: list[str], rows: list[list]) -> str:
        import csv
        import io
        buf = io.StringIO()
        buf.write("﻿")  # BOM
        writer = csv.writer(buf)
        writer.writerow(header)
        writer.writerows(rows)
        return buf.getvalue()

    async def export_customers_csv(self, user: User) -> str:
        stmt = select(Customer)
        if user.user_type != "MANAGER":
            stmt = stmt.where(Customer.owner_employee_id == user.id)
        stmt = stmt.order_by(Customer.created_at.desc())
        customers = list((await self.db.execute(stmt)).scalars().all())
        return self._to_csv(
            ["客户ID", "姓名", "手机号", "状态", "来源渠道", "归属员工ID", "创建时间"],
            [[c.id, c.name, c.phone, c.status, c.source_channel, c.owner_employee_id,
              c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""] for c in customers],
        )

    async def export_reports_csv(self, user: User, start: date | None, end: date | None) -> str:
        stmt = select(EmployeeDailyReport)
        if user.user_type != "MANAGER":
            stmt = stmt.where(EmployeeDailyReport.employee_id == user.id)
        if start:
            stmt = stmt.where(EmployeeDailyReport.report_date >= start)
        if end:
            stmt = stmt.where(EmployeeDailyReport.report_date <= end)
        stmt = stmt.order_by(EmployeeDailyReport.report_date.desc())
        reports = list((await self.db.execute(stmt)).scalars().all())
        return self._to_csv(
            ["日报ID", "员工ID", "日期", "状态", "是否迟报", "内容"],
            [[r.id, r.employee_id, str(r.report_date), r.status, "是" if r.is_late else "否", r.content] for r in reports],
        )

    async def export_followups_csv(self, user: User) -> str:
        from app.models.crm import CrmFollowUp
        stmt = select(CrmFollowUp)
        if user.user_type != "MANAGER":
            stmt = stmt.where(CrmFollowUp.employee_id == user.id)
        stmt = stmt.order_by(CrmFollowUp.created_at.desc())
        follows = list((await self.db.execute(stmt)).scalars().all())
        return self._to_csv(
            ["跟进ID", "客户ID", "员工ID", "跟进方式", "跟进内容", "下次跟进日期", "创建时间"],
            [[f.id, f.customer_id, f.employee_id, f.follow_type, f.content,
              str(f.next_date) if f.next_date else "",
              f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else ""] for f in follows],
        )

    async def export_tickets_csv(self, user: User, status: str | None) -> str:
        """导出投诉记录 CSV（v6.6.0，对齐需求"客户列表、日报、投诉记录"三项导出口径）。"""
        from app.models.student import StudentFeedbackTicket
        stmt = select(StudentFeedbackTicket)
        if status:
            stmt = stmt.where(StudentFeedbackTicket.status == status)
        stmt = stmt.order_by(StudentFeedbackTicket.create_time.desc())
        tickets = list((await self.db.execute(stmt)).scalars().all())
        return self._to_csv(
            ["工单ID", "学生ID", "内容", "状态", "解决方案", "创建时间"],
            [[t.id, t.student_id, t.content, t.status,
              t.solution if t.solution else "",
              t.create_time.strftime("%Y-%m-%d %H:%M") if t.create_time else ""] for t in tickets],
        )

    # ── 组织架构成员 + 电话脱敏（v6.6.0） ────────────────
    @staticmethod
    def mask_phone(phone: str | None) -> str | None:
        if not phone or len(phone) < 7:
            return phone
        return f"{phone[:3]}****{phone[-4:]}"

    async def list_org_members(
        self, department: str | None, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[User], int]:
        """按部门/姓名查同事，电话脱敏返回。"""
        stmt = select(User).where(User.user_type.in_(["EMPLOYEE", "MANAGER"]))
        count_stmt = select(func.count()).select_from(User).where(User.user_type.in_(["EMPLOYEE", "MANAGER"]))
        if department:
            stmt = stmt.where(User.department == department)
            count_stmt = count_stmt.where(User.department == department)
        if keyword:
            stmt = stmt.where(User.real_name.like(f"%{keyword}%"))
            count_stmt = count_stmt.where(User.real_name.like(f"%{keyword}%"))
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        users = list((await self.db.execute(stmt)).scalars().all())
        return users, total

    async def reveal_member_phone(self, user_id: int, operator: User) -> dict:
        """二次确认后返回完整电话，写操作日志留痕（敏感操作审计）。"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        target = result.scalar_one_or_none()
        if not target or target.user_type not in ("EMPLOYEE", "MANAGER"):
            raise NotFoundError(message="同事不存在")
        from app.models.system import SysOperationLog
        self.db.add(SysOperationLog(
            user_id=operator.id,
            module="M3",
            action="phone_reveal",
            target_type="user",
            target_id=user_id,
            detail={"target_real_name": target.real_name},
        ))
        await self.db.commit()
        return {"user_id": target.id, "real_name": target.real_name, "phone": target.phone}

    async def list_operation_logs(
        self,
        action_type: str | None,
        operator_id: int | None,
        start: date | None,
        end: date | None,
        page: int,
        page_size: int,
    ) -> tuple[list, int]:
        """操作日志查询（MANAGER，Phase 1.3 管理层端）。"""
        from app.models.system import SysOperationLog
        stmt = select(SysOperationLog)
        count_stmt = select(func.count()).select_from(SysOperationLog)
        if action_type:
            stmt = stmt.where(SysOperationLog.action == action_type)
            count_stmt = count_stmt.where(SysOperationLog.action == action_type)
        if operator_id is not None:
            stmt = stmt.where(SysOperationLog.user_id == operator_id)
            count_stmt = count_stmt.where(SysOperationLog.user_id == operator_id)
        if start:
            stmt = stmt.where(SysOperationLog.created_at >= start)
            count_stmt = count_stmt.where(SysOperationLog.created_at >= start)
        if end:
            stmt = stmt.where(SysOperationLog.created_at < end + timedelta(days=1))
            count_stmt = count_stmt.where(SysOperationLog.created_at < end + timedelta(days=1))
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(SysOperationLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        logs = list((await self.db.execute(stmt)).scalars().all())
        return logs, total

    # ── 企业智能助手 Agent（权限感知 + 降级） ─────────────
    EMPLOYEE_CAPABILITIES: list[str] = [
        "客户信息查询（仅自己名下）",
        "客户信息录入（文字/PDF/照片/Word/Excel）",
        "客户跟进记录",
        "待办事项提醒",
        "组织架构查询",
        "新人指引",
        "口述日报",
        "指令式业务处理（二次确认后执行）",
    ]
    MANAGER_EXTRA_CAPABILITIES: list[str] = [
        "全域客户查询（不受数据隔离限制）",
        "经营状况查询与数据分析",
        "流程审批",
        "员工管理",
        "日报汇总查看",
        "智能报告查询",
    ]

    async def _factual_snapshot(self, user: User) -> dict:
        """按角色产出「事实快照」：仅含该角色权限内的真实聚合数据，供 Agent 照实作答。

        只给聚合口径（计数与分布），不含客户/学生明细，避免越权与请求体积膨胀。
        """
        if user.user_type == "MANAGER":
            # 管理层：全域经营聚合（客户 6 态分布/漏斗/渠道/转化率/日报/审批/投诉/心理）
            return {"scope": "全域（不受数据隔离限制）", "dashboard": await self.dashboard()}

        # 普通员工：本人待办与到期跟进 + 名下客户状态分布
        reminders = await self.get_reminders(user)
        status_rows = (await self.db.execute(
            select(Customer.status, func.count())
            .where(Customer.owner_employee_id == user.id)
            .group_by(Customer.status)
        )).all()
        by_status = {(st or "未知"): cnt for st, cnt in status_rows}
        return {
            "scope": "仅本人名下",
            "reminders": reminders,
            "my_customers_by_status": by_status,
            "my_customers_total": sum(by_status.values()),
        }

    @staticmethod
    def _snapshot_reply(user: User, snapshot: dict) -> str:
        """AI 不可用时的确定性降级：直接用事实快照拼摘要，不编造、不空谈能力。"""
        lines = [f"AI 助手暂时不可用（Dify 未连接）。以下为你的真实数据（{snapshot.get('scope')}）："]
        if user.user_type == "MANAGER":
            dash = snapshot.get("dashboard") or {}
            cust = dash.get("customers") or {}
            overview = dash.get("overview") or {}
            reports = dash.get("reports") or {}
            approvals = dash.get("approvals") or {}
            so = cust.get("status_overview") or {}
            lines.append(f"- 客户总数：{cust.get('total', '数据不可得')}")
            lines.append("- 期末状态：" + " / ".join(
                f"{k} {so.get(k, '—')}" for k in ("NEW", "FOLLOWING", "STRONG", "SIGNED", "ENROLLED", "LOST")
            ))
            lines.append(f"- 本月新增：{cust.get('new_this_month', '—')}；转化率：{overview.get('conversion_rate', '—')}%；"
                         f"在办学生：{overview.get('active_students', '—')}")
            lines.append(f"- 日报：今日已交 {reports.get('today_submitted', '—')}；本月已交 {reports.get('month_submitted', '—')}；"
                         f"本月迟报 {reports.get('late_this_month', '—')}")
            lines.append(f"- 待审批：{approvals.get('pending_total', '—')}")
            lines.append("- 更多维度请在「经营看板 / 智能汇总 / 日报管理」页面查看。")
        else:
            reminders = snapshot.get("reminders") or {}
            lines.append(f"- 我的客户：{snapshot.get('my_customers_total', 0)} 个")
            by_status = snapshot.get("my_customers_by_status") or {}
            if by_status:
                lines.append("- 状态分布：" + " / ".join(f"{k} {v}" for k, v in by_status.items()))
            lines.append(f"- 待办 {reminders.get('todos_pending', '—')} 项；"
                         f"到期跟进 {reminders.get('follow_ups_due', '—')} 项")
        return "\n".join(lines)

    async def _build_agent_real_data(self, user: User) -> str:
        """实时业务快照（v6.11.26）：注入给 Dify，让助手基于真实数据回答，杜绝编造。

        v6.11.50：MANAGER 追加全域经营摘要行（复用经营看板 dashboard() 聚合，口径一致），
        使管理层 Agent 可直接回答经营情况；EMPLOYEE 维持本人维度不变。
        """
        from sqlalchemy import func, select

        from app.models.customer import Customer
        from app.models.employee import EmployeeTodo
        from app.models.system import ApprovalInstance

        rows = (await self.db.execute(
            select(EmployeeTodo).where(
                EmployeeTodo.employee_id == user.id, EmployeeTodo.status == "pending"
            ).order_by(EmployeeTodo.due_time).limit(5)
        )).scalars().all()
        todo_txt = "；".join(
            f"{r.title}（优先级{r.priority}，截止{r.due_time or '未定'}）" for r in rows
        ) or "无"
        q = select(func.count()).select_from(Customer)
        if user.user_type != "MANAGER":
            q = q.where(Customer.owner_employee_id == user.id)
        cust_cnt = (await self.db.execute(q)).scalar() or 0
        pend_cnt = (await self.db.execute(
            select(func.count()).select_from(ApprovalInstance).where(ApprovalInstance.status == "pending")
        )).scalar() or 0
        base = f"今日待办：{todo_txt}｜名下客户数：{cust_cnt}｜待审批申请数：{pend_cnt}"
        if user.user_type != "MANAGER":
            return base
        # 管理层：追加全域经营摘要（query 通道为唯一事实源，v6.11.50）
        try:
            dash = await self.dashboard()
        except Exception as dash_exc:
            logger.warning("agent ops summary failed: user=%s err=%s", user.id, dash_exc)
            return base
        cust = dash.get("customers") or {}
        overview = dash.get("overview") or {}
        reports = dash.get("reports") or {}
        approvals = dash.get("approvals") or {}
        tickets = dash.get("tickets") or {}
        psych = dash.get("psych_alerts") or {}
        so = cust.get("status_overview") or {}
        stage_cn = {
            "NEW": "新录入", "FOLLOWING": "跟进中", "STRONG": "意向强烈",
            "SIGNED": "已签约", "ENROLLED": "已入学", "LOST": "已流失",
        }
        status_txt = " / ".join(f"{stage_cn[k]}{so.get(k, '—')}" for k in stage_cn)
        by_source = cust.get("by_source") or []
        src_txt = "、".join(f"{r.get('source')}{r.get('count')}" for r in by_source[:3]) if by_source else "—"
        signed = overview.get("signed_amount")
        signed_txt = f"{signed}（按已定价学费估算）" if signed is not None else "暂无（学费未定价）"
        ops = (
            f"经营摘要（全域）：客户总数 {cust.get('total', '—')}；本月新增 {cust.get('new_this_month', '—')}；"
            f"期末状态分布：{status_txt}；累计转化率 {overview.get('conversion_rate', '—')}%；"
            f"在办学生 {overview.get('active_students', '—')}；签约金额（估）{signed_txt}；"
            f"日报：今日已交 {reports.get('today_submitted', '—')}/本月已交 {reports.get('month_submitted', '—')}"
            f"/本月迟报 {reports.get('late_this_month', '—')}；待审批 {approvals.get('pending_total', '—')}；"
            f"待处理投诉 {tickets.get('pending', '—')}；未处理心理预警 {psych.get('unhandled', '—')}；"
            f"来源渠道Top3：{src_txt}"
        )
        return base + "｜" + ops

    @staticmethod
    def _strip_agent_json(reply: str) -> str:
        """剥离回复中的 JSON/结构化 action 残留（v6.11.26 兜底），只留自然语言。"""
        import re

        out = re.sub(r"```(?:json)?\s*.*?```", "", reply, flags=re.S).strip()
        if out.startswith("{") or out.startswith("["):
            try:
                import json as _json
                _json.loads(out)
                return "已收到您的指令。为避免误操作，指令式业务请走二次确认流程（我已识别到结构化动作），或直接用自然语言描述需求。"
            except Exception:
                pass
        return out or "（回复为空）"

    async def agent_chat(self, user: User, message: str, session_id: str | None) -> dict:
        """企业助手会话：按角色注入权限感知 context 转发 Dify；AI 不可用降级返回能力清单。

        权限感知：EMPLOYEE 数据范围=own（仅名下客户），MANAGER=all（全域），
        能力清单写入 inputs.capabilities 供 Dify Agent prompt 使用。
        v6.11.26（master）：注入实时业务快照（待办/客户/审批）+ 回复格式约束，禁止编造与 JSON 输出。
        本线差异字段：追加 factual_data 事实快照与 factual_rule 防编造约束（供 prompt 变量引用），
        AI 全链路不可用时用 _snapshot_reply 做确定性降级。
        """
        from app.services.ai_service import AgentType, ai_service

        caps = list(self.EMPLOYEE_CAPABILITIES)
        if user.user_type == "MANAGER":
            caps += self.MANAGER_EXTRA_CAPABILITIES
        snapshot = await self._factual_snapshot(user)
        context = {
            "user_type": user.user_type,
            "user_id": str(user.id),
            "real_name": user.real_name or user.username,
            "data_scope": "all" if user.user_type == "MANAGER" else "own",
            "capabilities": "、".join(caps),
            "factual_data": json.dumps(snapshot, ensure_ascii=False),
            "factual_rule": "只能引用 factual_data 中的数字与分布作答；其中没有的维度禁止编造，"
                            "改为指引用户到对应页面查看。",
        }
        try:
            real = await self._build_agent_real_data(user)
        except Exception as snap_exc:  # 快照失败不阻塞对话
            logger.warning("agent real-data snapshot failed: user=%s err=%s", user.id, snap_exc)
            real = "（实时数据暂不可用，请勿编造具体事项）"
        prompt_message = (
            "【系统注入·实时数据】以下是你唯一可引用的事实依据，禁止编造其中没有的人名/单号/事项；"
            "用户问题超出数据范围时如实说明没有数据：\n"
            f"{real}\n"
            "【回复格式】只用自然语言回答，禁止输出 JSON、结构化 action 或代码块。\n"
            f"【用户提问】{message}"
        )
        try:
            resp = await ai_service.chat(
                agent=AgentType.EMPLOYEE,
                message=prompt_message,
                session_id=session_id or "new",
                user_id=f"employee_{user.id}",
                context=context,
            )
            return {"reply": self._strip_agent_json(resp.content), "session_id": resp.session_id, "source": "dify"}
        except Exception:
            try:
                from app.services.model_ai_service import model_ai_service
                result = await model_ai_service.chat(prompt_message, session_id or "new", context)
                return {"reply": self._strip_agent_json(result["reply"]), "session_id": result.get("session_id", session_id or "new"), "source": "model"}
            except Exception as model_exc:
                logger.warning("model fallback failed: employee=%s error=%s", user.id, model_exc)
            return {"reply": self._snapshot_reply(user, snapshot),
                    "session_id": session_id or "new", "source": "fallback"}

    async def agent_chat_stream(self, user: User, message: str, session_id: str | None) -> AsyncIterator[dict]:
        """企业助手流式会话：按角色注入权限感知 context 转发 Dify 流式；AI 不可用降级返回能力清单。

        v6.11.38：SSE 增量下发（感知延迟=首字时间），事件格式与客服流式对齐：
        {"event":"meta","conversation_id"} / {"event":"token","delta"} / {"event":"done","data"}。
        权限感知：EMPLOYEE 数据范围=own（仅名下客户），MANAGER=all（全域），
        能力清单写入 inputs.capabilities 供 Dify Agent prompt 使用。
        """
        from app.services.ai_service import AgentType, ai_service

        caps = list(self.EMPLOYEE_CAPABILITIES)
        if user.user_type == "MANAGER":
            caps += self.MANAGER_EXTRA_CAPABILITIES
        snapshot = await self._factual_snapshot(user)
        context = {
            "user_type": user.user_type,
            "user_id": str(user.id),
            "real_name": user.real_name or user.username,
            "data_scope": "all" if user.user_type == "MANAGER" else "own",
            "capabilities": "、".join(caps),
            "factual_data": json.dumps(snapshot, ensure_ascii=False),
            "factual_rule": "只能引用 factual_data 中的数字与分布作答；其中没有的维度禁止编造，"
                            "改为指引用户到对应页面查看。",
        }
        try:
            real = await self._build_agent_real_data(user)
        except Exception as snap_exc:
            logger.warning("agent real-data snapshot failed: user=%s err=%s", user.id, snap_exc)
            real = "（实时数据暂不可用，请勿编造具体事项）"
        prompt_message = (
            "【系统注入·实时数据】以下是你唯一可引用的事实依据，禁止编造其中没有的人名/单号/事项；"
            "用户问题超出数据范围时如实说明没有数据：\n"
            f"{real}\n"
            "【回复格式】只用自然语言回答，禁止输出 JSON、结构化 action 或代码块。\n"
            f"【用户提问】{message}"
        )
        yield {"event": "meta", "conversation_id": session_id or "new"}

        buf = ""
        dify_session_id = session_id or "new"
        stream_error: Exception | None = None
        try:
            async for token in ai_service.chat_stream(
                agent=AgentType.EMPLOYEE,
                message=prompt_message,
                session_id=session_id or "new",
                user_id=f"employee_{user.id}",
                context=context,
            ):
                buf += token
                yield {"event": "token", "delta": token}
        except Exception as exc:
            stream_error = exc
            logger.warning("employee agent chat_stream failed: user=%s error=%s", user.id, exc)

        # 流失败或无输出时走降级链
        if stream_error is not None or not buf:
            try:
                from app.services.model_ai_service import model_ai_service
                result = await model_ai_service.chat(prompt_message, session_id or "new", context)
                buf = self._strip_agent_json(result["reply"])
                dify_session_id = result.get("session_id", session_id or "new")
                yield {"event": "token", "delta": buf}
            except Exception as model_exc:
                logger.warning("model fallback failed: employee=%s error=%s", user.id, model_exc)
                buf = self._snapshot_reply(user, snapshot)
                yield {"event": "token", "delta": buf}

        yield {"event": "done", "data": {"reply": buf, "session_id": dify_session_id, "source": "stream"}}

    # ── 新人指引问答（RAG 优先，本地静态降级） ────────────
    async def guide_ask(self, user: User, question: str, session_id: str | None) -> dict:
        """优先走 Dify RAG（知识库挂载新人手册，scene=newcomer_guide）；
        AI 不可用降级为本地静态指引关键词匹配。"""
        from app.services.ai_service import AgentType, ai_service
        from app.services.onboarding_guide import search_guide

        try:
            resp = await ai_service.chat(
                agent=AgentType.EMPLOYEE,
                message=question,
                session_id=session_id or "new",
                user_id=f"employee_{user.id}",
                context={"scene": "newcomer_guide"},
            )
            return {"answer": resp.content, "source": "dify", "session_id": resp.session_id}
        except Exception:
            try:
                from app.services.model_ai_service import model_ai_service
                result = await model_ai_service.chat(question, session_id or "new", {"scene": "newcomer_guide"})
                return {"answer": result["reply"], "source": "model", "session_id": result.get("session_id", session_id or "new")}
            except Exception as model_exc:
                logger.warning("guide model fallback failed: user=%s error=%s", user.id, model_exc)
            hits = search_guide(question)
            if hits:
                parts = [f"【{h['section']}】{h['q']}\n{h['a']}" for h in hits[:3]]
                answer = "以下为新人指南中的相关内容（本地匹配）：\n\n" + "\n\n".join(parts)
            else:
                answer = ("新人指南中暂未找到相关内容，可联系入职导师或行政办公室"
                          "（林雅婷，分机 8001）获取帮助。")
            return {"answer": answer, "source": "local", "session_id": session_id or "new"}

    # ── 提醒聚合（登录拉取，主动提醒的数据源） ────────────
    async def get_reminders(self, user: User) -> dict:
        """聚合：未完成待办 / 今日应跟进客户 / 待我审批行政服务 / 未处理心理预警；
        MANAGER 额外返回待我审批的审批单数。"""
        from app.models.crm import CrmFollowUp
        from app.models.student import StudentAdminService, StudentPsychAlert

        todos_pending = (await self.db.execute(
            select(func.count()).select_from(EmployeeTodo).where(
                EmployeeTodo.employee_id == user.id,
                EmployeeTodo.status == "pending",
            )
        )).scalar_one()

        follow_stmt = select(func.count()).select_from(CrmFollowUp).where(
            CrmFollowUp.next_date.is_not(None),
            CrmFollowUp.next_date <= date.today(),
        )
        if user.user_type != "MANAGER":
            follow_stmt = follow_stmt.where(CrmFollowUp.employee_id == user.id)
        follow_ups_due = (await self.db.execute(follow_stmt)).scalar_one()

        admin_pending = (await self.db.execute(
            select(func.count()).select_from(StudentAdminService).where(
                StudentAdminService.approver_id == user.id,
                StudentAdminService.status == "待审批",
            )
        )).scalar_one()

        # 员工只看本人负责学员的未处理预警，与 GET /employee/psych-alerts 的列表口径保持一致；
        # MANAGER 仍看全量（v6.11.39 修复：此前未过滤，员工端计数恒为全量、与列表对不上）。
        psych_stmt = select(func.count()).select_from(StudentPsychAlert).where(
            StudentPsychAlert.status == "未处理"
        )
        if user.user_type != "MANAGER":
            owned_students = select(Customer.sys_user_id).where(Customer.owner_employee_id == user.id)
            psych_stmt = psych_stmt.where(StudentPsychAlert.student_id.in_(owned_students))
        psych_pending = (await self.db.execute(psych_stmt)).scalar_one()

        result: dict = {
            "todos_pending": todos_pending,
            "follow_ups_due": follow_ups_due,
            "admin_services_pending": admin_pending,
            "psych_alerts_pending": psych_pending,
            "approvals_pending": None,
        }
        if user.user_type == "MANAGER":
            from app.models.system import ApprovalTask
            from app.services.approval_engine import TaskStatus
            result["approvals_pending"] = (await self.db.execute(
                select(func.count()).select_from(ApprovalTask).where(
                    ApprovalTask.approver_id == user.id,
                    ApprovalTask.status == TaskStatus.PENDING.value,
                )
            )).scalar_one()
        return result

    # ── 经营看板（MANAGER，Phase 1.3） ───────────────────
    DASHBOARD_STAGE_ALIASES: dict[str, list[str]] = {
        "新录入": ["新录入", "NEW"],
        "跟进中": ["跟进中", "FOLLOWING"],
        "意向强烈": ["意向强烈", "STRONG"],
        "已签约": ["已签约", "SIGNED", "CONVERTED"],
        "已入学": ["已入学", "ENROLLED"],
    }
    LOST_ALIASES = ["已流失", "LOST"]

    async def dashboard(self) -> dict:
        """经营看板：全域客户数据 + 转化漏斗 + 审批/日报/投诉/心理预警聚合。"""
        from app.models.student import StudentFeedbackTicket, StudentPsychAlert
        from app.models.system import ApprovalInstance
        from app.services.approval_engine import ApprovalStatus

        now = datetime.now()
        today = now.date()
        month_start = today.replace(day=1)

        # ── 客户全域数据 ──
        total = (await self.db.execute(
            select(func.count()).select_from(Customer)
        )).scalar_one()
        new_this_month = (await self.db.execute(
            select(func.count()).select_from(Customer).where(Customer.created_at >= month_start)
        )).scalar_one()
        status_counts = dict((await self.db.execute(
            select(Customer.status, func.count()).group_by(Customer.status)
        )).all())
        funnel = [
            {"stage": stage, "count": sum(status_counts.get(a, 0) for a in aliases)}
            for stage, aliases in self.DASHBOARD_STAGE_ALIASES.items()
        ]
        lost = sum(status_counts.get(a, 0) for a in self.LOST_ALIASES)
        by_source = [
            {"source": row[0] or "unknown", "count": row[1]}
            for row in (await self.db.execute(
                select(Customer.source_channel, func.count())
                .group_by(Customer.source_channel)
                .order_by(func.count().desc())
            )).all()
        ]

        # ── 审批聚合 ──
        pending_by_biz_type = dict((await self.db.execute(
            select(ApprovalInstance.biz_type, func.count()).where(
                ApprovalInstance.status == ApprovalStatus.PENDING.value
            ).group_by(ApprovalInstance.biz_type)
        )).all())

        # ── 日报 ──
        today_submitted = (await self.db.execute(
            select(func.count()).select_from(EmployeeDailyReport).where(
                EmployeeDailyReport.report_date == today,
                EmployeeDailyReport.status == "submitted",
            )
        )).scalar_one()
        month_submitted = (await self.db.execute(
            select(func.count()).select_from(EmployeeDailyReport).where(
                EmployeeDailyReport.report_date >= month_start,
                EmployeeDailyReport.status == "submitted",
            )
        )).scalar_one()
        late_this_month = (await self.db.execute(
            select(func.count()).select_from(EmployeeDailyReport).where(
                EmployeeDailyReport.is_late.is_(True),
                EmployeeDailyReport.report_date >= month_start,
            )
        )).scalar_one()

        # ── 投诉 + 心理预警 ──
        tickets_pending = (await self.db.execute(
            select(func.count()).select_from(StudentFeedbackTicket).where(
                StudentFeedbackTicket.status == "待处理"
            )
        )).scalar_one()
        tickets_handled_month = (await self.db.execute(
            select(func.count()).select_from(StudentFeedbackTicket).where(
                StudentFeedbackTicket.status == "已处理",
                StudentFeedbackTicket.update_time >= month_start,
            )
        )).scalar_one()
        psych_unhandled = (await self.db.execute(
            select(func.count()).select_from(StudentPsychAlert).where(
                StudentPsychAlert.status == "未处理"
            )
        )).scalar_one()

        # ── 业绩概览（本月新增意向/转化率/在办学生数/投诉率） ──
        # 对齐《promts/智能报告/report_package/02_一期指标口径表V1.md》：
        # 期末意向=新录入+跟进中+意向强烈；期末成交=已签约+已入学；期末流失=已流失
        intent = funnel[0]["count"] + funnel[1]["count"] + funnel[2]["count"]
        converted = funnel[-1]["count"] + funnel[-2]["count"]  # 已入学 + 已签约
        conversion_rate = round(converted / total * 100, 2) if total else 0.0
        active_students = (await self.db.execute(
            select(func.count()).select_from(User).where(
                User.user_type == "STUDENT", User.status == "正常"
            )
        )).scalar_one()
        tickets_total = (await self.db.execute(
            select(func.count()).select_from(StudentFeedbackTicket)
        )).scalar_one()
        complaint_rate = round(tickets_total / active_students * 100, 2) if active_students else 0.0

        # 新增去向（口径表：本期新增客户按期末状态分为仍意向/已签约/已入学/已流失，合计=新增数）
        new_status_rows = (await self.db.execute(
            select(Customer.status).where(Customer.created_at >= month_start)
        )).all()
        new_outcomes = {"intent": 0, "signed": 0, "enrolled": 0, "lost": 0}
        for (st,) in new_status_rows:
            if st in ("已签约", "SIGNED", "CONVERTED"):
                new_outcomes["signed"] += 1
            elif st in ("已入学", "ENROLLED"):
                new_outcomes["enrolled"] += 1
            elif st in ("已流失", "LOST"):
                new_outcomes["lost"] += 1
            else:
                new_outcomes["intent"] += 1  # 未签约未流失即仍意向

        # 期末状态总览（与 M5 报告 status_overview 统一名称与结构，英文 6 态键）
        status_overview = {
            "NEW": funnel[0]["count"],
            "FOLLOWING": funnel[1]["count"],
            "STRONG": funnel[2]["count"],
            "SIGNED": funnel[3]["count"],
            "ENROLLED": funnel[4]["count"],
            "LOST": lost,
            "total": total,
            "intent": intent,
            "converted": converted,
            "lost": lost,
        }

        # ── 签约金额（v6.11.45） ──
        # 口径：成交客户数（已签约+已入学）× 项目学费。
        # 数据现状：course_project 中仅「新加坡国际本硕升学计划」已定价，其余项目学费为空
        # （免学费/按方案确定），且客户侧没有「意向项目」落库字段（研判 recommended_json /
        # matched_programs_json 全为空、study_intent 多为空），无法逐单匹配，故按当前唯一
        # 已定价项目的学费估算；已定价学费不唯一或全部未定价时返回 None（前端显示暂无数据）。
        priced_fees = set((await self.db.execute(
            select(CourseProject.tuition_fee).where(CourseProject.tuition_fee.isnot(None))
        )).scalars().all())
        unit_price = float(next(iter(priced_fees))) if len(priced_fees) == 1 else None
        signed_amount = round(converted * unit_price, 2) if unit_price is not None else None

        return {
            "overview": {
                "new_prospects_this_month": new_this_month,
                "new_this_period": new_this_month,
                "conversion_rate": conversion_rate,
                "active_students": active_students,
                "complaint_rate": complaint_rate,
                "intent": intent,
                "converted": converted,
                "lost": lost,
                "new_outcomes": new_outcomes,
                "signed_amount": signed_amount,
                "signed_amount_unit": unit_price,
                "signed_amount_basis": "已签约+已入学客户数 × 已定价项目学费",
            },
            "customers": {
                "total": total,
                "new_this_month": new_this_month,
                "new_this_period": new_this_month,
                "by_status": status_counts,
                "status_overview": status_overview,
                "by_source": by_source,
                "funnel": funnel,
                "lost": lost,
            },
            "approvals": {
                "pending_total": sum(pending_by_biz_type.values()),
                "pending_by_biz_type": pending_by_biz_type,
            },
            "reports": {
                "today_submitted": today_submitted,
                "month_submitted": month_submitted,
                "late_this_month": late_this_month,
            },
            "tickets": {
                "pending": tickets_pending,
                "handled_this_month": tickets_handled_month,
            },
            "psych_alerts": {
                "unhandled": psych_unhandled,
            },
        }

    # ── 审批中心（MANAGER，Phase 1.3） ───────────────────
    async def approvals_center(
        self, biz_type: str | None, status: str | None, page: int, page_size: int
    ) -> dict:
        """审批中心聚合视图：全量审批单（不限于本人审批）+ 各类型待审统计。"""
        from app.models.system import ApprovalInstance
        from app.schemas.approval import ApprovalInstanceOut, ApprovalTaskOut
        from app.services.approval_engine import ApprovalStatus

        stmt = select(ApprovalInstance)
        count_stmt = select(func.count()).select_from(ApprovalInstance)
        if biz_type:
            stmt = stmt.where(ApprovalInstance.biz_type == biz_type)
            count_stmt = count_stmt.where(ApprovalInstance.biz_type == biz_type)
        if status:
            stmt = stmt.where(ApprovalInstance.status == status)
            count_stmt = count_stmt.where(ApprovalInstance.status == status)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ApprovalInstance.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        instances = list((await self.db.execute(stmt)).scalars().all())

        pending_by_biz_type = dict((await self.db.execute(
            select(ApprovalInstance.biz_type, func.count()).where(
                ApprovalInstance.status == ApprovalStatus.PENDING.value
            ).group_by(ApprovalInstance.biz_type)
        )).all())

        items = []
        for inst in instances:
            tasks = await approval_engine.get_tasks(inst.id)
            item = ApprovalInstanceOut.model_validate(inst)
            item.tasks = [ApprovalTaskOut.model_validate(t) for t in tasks]
            items.append(item)
        return {
            "stats": {
                "pending_total": sum(pending_by_biz_type.values()),
                "pending_by_biz_type": pending_by_biz_type,
            },
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── 用户管理（MANAGER，Phase 1.3） ───────────────────
    async def list_users(
        self, user_type: str | None, status: str | None, keyword: str | None, page: int, page_size: int
    ) -> tuple[list[User], int]:
        """用户列表（管理视角，含 permissions JSON），username/real_name 模糊。"""
        stmt = select(User).where(User.user_type.in_(["EMPLOYEE", "MANAGER"]))
        count_stmt = select(func.count()).select_from(User).where(User.user_type.in_(["EMPLOYEE", "MANAGER"]))
        if user_type:
            stmt = stmt.where(User.user_type == user_type)
            count_stmt = count_stmt.where(User.user_type == user_type)
        if status:
            stmt = stmt.where(User.status == status)
            count_stmt = count_stmt.where(User.status == status)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(User.username.like(like) | User.real_name.like(like))
            count_stmt = count_stmt.where(User.username.like(like) | User.real_name.like(like))
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        users = list((await self.db.execute(stmt)).scalars().all())
        return users, total

    async def create_user(self, data: dict) -> User:
        """创建员工/管理层账号（管理层账号来源规则：MANAGER 创建）。"""
        from app.core.security import hash_password

        existing = (await self.db.execute(select(User).where(User.username == data["username"]))).scalar_one_or_none()
        if existing:
            raise ConflictError(message=f"用户名 {data['username']} 已存在")
        if data.get("phone"):
            phone_exists = (await self.db.execute(select(User).where(User.phone == data["phone"]))).scalar_one_or_none()
            if phone_exists:
                raise BusinessError(code=40004, message="手机号已注册")

        user = User(
            username=data["username"],
            password_hash=hash_password(data["password"]),
            real_name=data["real_name"],
            user_type=data["user_type"],
            phone=data.get("phone"),
            employee_role=data.get("employee_role"),
            department=data.get("department"),
            permissions=data.get("permissions"),
            status="正常",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _get_managed_user(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.user_type not in ("EMPLOYEE", "MANAGER"):
            raise NotFoundError(message="用户不存在")
        return user

    async def update_user_status(self, operator_id: int, user_id: int, status: str) -> User:
        """启用/禁用账号（禁用后登录返回 40003），写操作日志。"""
        target = await self._get_managed_user(user_id)
        if target.id == operator_id and status == "禁用":
            raise BusinessError(code=40002, message="不能禁用自己的账号")
        if target.status == status:
            raise ConflictError(message=f"账号已是「{status}」状态")
        old_status = target.status
        target.status = status
        from app.models.system import SysOperationLog
        self.db.add(SysOperationLog(
            user_id=operator_id,
            module="M3",
            action="user_status_change",
            target_type="user",
            target_id=user_id,
            detail={"target_username": target.username, "old_status": old_status, "new_status": status},
        ))
        await self.db.commit()
        await self.db.refresh(target)
        return target

    async def update_user_permissions(self, operator_id: int, user_id: int, permissions: list[str]) -> User:
        """配置用户额外权限（覆盖式写入 sys_user.permissions JSON），写操作日志。"""
        target = await self._get_managed_user(user_id)
        old = target.permissions
        target.permissions = permissions
        from app.models.system import SysOperationLog
        self.db.add(SysOperationLog(
            user_id=operator_id,
            module="M3",
            action="user_permissions_change",
            target_type="user",
            target_id=user_id,
            detail={"target_username": target.username, "old": old, "new": permissions},
        ))
        await self.db.commit()
        await self.db.refresh(target)
        return target
