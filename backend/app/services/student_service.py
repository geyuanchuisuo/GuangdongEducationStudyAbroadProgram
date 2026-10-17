"""M4 学生模块 Service（v6.8.0）

边界说明：
- 学生端提交请假只写 student_admin_service（status=待审批），不触碰 M0 审批引擎——
  M3 员工审批侧（employee_service.submit_admin_service）已兜底补建审批实例。
- 心理预警创建后发布 psych_alert.created 事件（契约 source=M4），M3 已订阅生成待办。
- 进度追踪按 v2.5.0 契约由 M4 统一实现员工端更新+学生端查看。
"""
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ConflictError, ForbiddenError, NotFoundError
from app.core.response import success_response  # noqa: F401  (风格占位，端点层使用)
from app.models.customer import Customer
from app.models.student import (
    StudentAcademic,
    StudentAdminService,
    StudentApplicationProgress,
    StudentFeedbackTicket,
    StudentPsychAlert,
    StudentPsychProfile,
    StudentScore,
)
from app.models.user import User
from app.schemas.student import (
    AdminServiceCreate,
    ProgressUpdate,
    TicketCreate,
)
from app.utils.logger import logger

# ── 进度追踪阶段枚举（一期固定 7 段） ──
PROGRESS_STAGES = ["选校", "文书", "申请", "面试", "offer", "签证", "入学"]

# ── 生活支持 FAQ（本地静态，Dify 知识库就绪后接 RAG） ──
LIFE_FAQS = [
    {"question": "初到德国怎么办理落户登记？", "answer": "抵达后两周内携带护照、租房合同到当地 Bürgeramt 办理 Anmeldung，老师会提前发预约指引，遇到问题可在群里或找负责老师协助。"},
    {"question": "海外生病了怎么办？", "answer": "轻微不适可在药店（Apotheke）购药；需要就医时先预约 Hausarzt（家庭医生），急诊拨 112。就医后保留单据便于保险报销，也可以随时联系我们协助。"},
    {"question": "手机卡和银行卡怎么办理？", "answer": "建议落地后先办预付卡应急（如 Lidl Connect），安顿后凭落户登记证明（Meldebescheinigung）去银行办理 Girokonto，我们提供陪同办理服务。"},
    {"question": "遇到签证/居留许可问题找谁？", "answer": "联系你的负责老师，我们会协助整理材料并预约外管局（Ausländerbehörde）办理。"},
    {"question": "如何联系国内家人最方便？", "answer": "德国电话卡通常含国内通话流量包，也可以使用微信语音；时差 6-7 小时，国内晚间是德国下午，适合通话。"},
    {"question": "生活上有紧急情况怎么办？", "answer": "紧急情况先拨打当地急救/报警电话（欧盟统一 112），第一时间联系负责老师并在平台提交反馈工单，我们会尽快响应。"},
]

# ── 更多服务（增值转化，不用业务术语，决策 #4） ──
MORE_SERVICES = [
    {"code": "tutoring", "name": "学业陪跑", "description": "一对一学业辅导与学习方法指导，帮你平稳过渡海外课堂。"},
    {"code": "language", "name": "语言加油站", "description": "德语/英语口语角与专项提升营，快速融入学习与生活。"},
    {"code": "career", "name": "职业领航", "description": "简历工作坊、模拟面试与实习内推信息，提前规划职业方向。"},
    {"code": "community", "name": "同城活动圈", "description": "跨校联谊、城市探索、节日聚会，认识更多同路人。"},
    {"code": "family", "name": "家长安心包", "description": "定期学业生活双报告，让家人实时了解你的近况。"},
]

# ── 心理情绪本地分析词库（AI 不可用时兜底，规则简单可测） ──
_NEGATIVE_KEYWORDS = ["压力", "焦虑", "失眠", "难过", "崩溃", "孤独", "想放弃", "emo", "撑不住", "绝望", "烦躁", "哭"]
_POSITIVE_KEYWORDS = ["开心", "顺利", "期待", "开心", "棒", "适应", "充实", "放松", "高兴", "满意"]
_DEGRADED_REPLY = (
    "我在呢，感谢你愿意和我分享。你的感受很重要，我会认真记录下来。"
    "如果此刻情绪比较强烈，可以先做几次深呼吸；我们会一起面对，必要时也可以联系你的负责老师聊聊。"
)


class StudentService:
    """学生模块业务逻辑（M4）。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 行政服务 ──
    async def submit_admin_service(self, student_id: int, data: AdminServiceCreate) -> StudentAdminService:
        """提交行政服务申请（请假等）。请假类型沿用 M3 的同学生防重规则（待审批/已通过即拒，40901）。"""
        if data.service_type == "请假":
            dup_result = await self.db.execute(
                select(StudentAdminService).where(
                    StudentAdminService.student_id == student_id,
                    StudentAdminService.service_type == "请假",
                    StudentAdminService.status.in_(["待审批", "已通过"]),
                )
            )
            if dup_result.scalars().first():
                raise ConflictError(message="你已有一条待审批或已通过的请假记录，请等待审批结果")

        svc = StudentAdminService(
            student_id=student_id,
            service_type=data.service_type,
            start_time=data.start_time,
            end_time=data.end_time,
            reason=data.reason,
            related_academic_id=data.related_academic_id,
            status="待审批",
        )
        self.db.add(svc)
        await self.db.commit()
        await self.db.refresh(svc)
        return svc

    async def list_admin_services(self, student_id: int, page: int, page_size: int) -> dict:
        total = (await self.db.execute(
            select(func.count()).select_from(StudentAdminService).where(StudentAdminService.student_id == student_id)
        )).scalar_one()
        items = (await self.db.execute(
            select(StudentAdminService)
            .where(StudentAdminService.student_id == student_id)
            .order_by(StudentAdminService.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ── 心理关怀 ──
    @staticmethod
    def _analyze_emotion(message: str) -> tuple[str, int]:
        """本地情绪启发式分析（稳定可测）：负面词-15/个，正面词+10/个，基线 60。"""
        score = 60
        neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in message)
        pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in message)
        score = max(10, min(95, score - neg * 15 + pos * 10))
        if score < 40:
            tag = "低落"
        elif score < 55:
            tag = "波动"
        elif score < 75:
            tag = "平稳"
        else:
            tag = "积极"
        return tag, score

    async def _upsert_profile(self, student_id: int, tag: str, score: int) -> StudentPsychProfile:
        result = await self.db.execute(
            select(StudentPsychProfile).where(StudentPsychProfile.student_id == student_id)
        )
        profile = result.scalar_one_or_none()
        entry = {"time": datetime.now(timezone.utc).isoformat(), "tag": tag, "score": score}
        if profile is None:
            profile = StudentPsychProfile(
                student_id=student_id,
                latest_emotion_tag=tag,
                emotion_score=score,
                last_interaction_time=datetime.now(timezone.utc),
                emotion_history=[entry],
            )
            self.db.add(profile)
        else:
            history = profile.emotion_history or []
            profile.emotion_history = (history + [entry])[-20:]
            profile.latest_emotion_tag = tag
            profile.emotion_score = score
            profile.last_interaction_time = datetime.now(timezone.utc)
        await self.db.flush()
        return profile

    async def psych_chat(self, student_id: int, message: str, session_id: str | None) -> dict:
        """AI 对话式情绪评估：AI 负责回复，本地规则负责量化落库；高危自动建预警并发布事件。"""
        ai = __import__("app.services.ai_service", fromlist=["AgentType", "ai_service"])
        reply = _DEGRADED_REPLY
        degraded = False
        sid = session_id or "new"
        try:
            resp = await ai.ai_service.chat(ai.AgentType.STUDENT, message, sid, user_id=str(student_id))
            reply, sid = resp.content, resp.session_id
        except Exception as exc:  # AI 网关不可用 → 本地降级（话术固定，不承诺任何结果）
            degraded = True
            logger.warning("psych_chat AI 降级: student=%s error=%s", student_id, exc)

        tag, score = self._analyze_emotion(message)
        await self._upsert_profile(student_id, tag, score)

        alert_created = False
        if score < 40:
            alert = StudentPsychAlert(
                student_id=student_id,
                trigger_reason=f"对话情绪评估低分（score={score}，tag={tag}）：{message[:100]}",
                risk_level="高" if score < 25 else "中",
                status="未处理",
            )
            self.db.add(alert)
            await self.db.flush()
            alert_created = True
            from app.services.event_bus import event_bus
            from app.services.event_contracts import EventType
            await event_bus.publish(
                EventType.PSYCH_ALERT_CREATED,
                source_module="M4",
                payload={"student_id": student_id, "risk_level": alert.risk_level, "reason": alert.trigger_reason},
            )

        await self.db.commit()
        return {
            "reply": reply,
            "session_id": sid,
            "emotion_tag": tag,
            "emotion_score": score,
            "alert_created": alert_created,
            "degraded": degraded,
        }

    async def get_profile(self, student_id: int) -> StudentPsychProfile | None:
        return (await self.db.execute(
            select(StudentPsychProfile).where(StudentPsychProfile.student_id == student_id)
        )).scalar_one_or_none()

    # ── 售后反馈 ──
    async def submit_ticket(self, student_id: int, data: TicketCreate) -> StudentFeedbackTicket:
        ticket = StudentFeedbackTicket(
            student_id=student_id,
            content=data.content,
            detail=data.detail,
            status="待处理",
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def list_tickets(self, student_id: int, page: int, page_size: int) -> dict:
        total = (await self.db.execute(
            select(func.count()).select_from(StudentFeedbackTicket).where(StudentFeedbackTicket.student_id == student_id)
        )).scalar_one()
        items = (await self.db.execute(
            select(StudentFeedbackTicket)
            .where(StudentFeedbackTicket.student_id == student_id)
            .order_by(StudentFeedbackTicket.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # ── 学业考务 ──
    async def get_academic(self, student_id: int) -> dict:
        now = datetime.now(timezone.utc)
        items = (await self.db.execute(
            select(StudentAcademic)
            .where(StudentAcademic.student_id == student_id)
            .order_by(StudentAcademic.due_time.asc())
        )).scalars().all()
        scores = (await self.db.execute(
            select(StudentScore)
            .where(StudentScore.student_id == student_id)
            .order_by(StudentScore.create_time.desc())
        )).scalars().all()

        score_values = [float(s.score) for s in scores]
        summary = {
            "count": len(score_values),
            "average": round(sum(score_values) / len(score_values), 2) if score_values else None,
            "highest": max(score_values) if score_values else None,
            "lowest": min(score_values) if score_values else None,
        }
        # DDL 前置提醒：3 天内到期且未发提醒的项由 Agent 第二批主动推送，此处仅标记 upcoming
        upcoming = [i.id for i in items if i.due_time >= now and (i.due_time - now).days <= 3]
        return {"academic_items": items, "scores": scores, "score_summary": summary, "upcoming_3d": upcoming}

    # ── 进度追踪（v2.5.0 契约：M4 统一实现员工端更新+学生端查看） ──
    async def get_progress(self, student_id: int) -> list[StudentApplicationProgress]:
        return list((await self.db.execute(
            select(StudentApplicationProgress)
            .where(StudentApplicationProgress.student_id == student_id)
            .order_by(StudentApplicationProgress.update_time.desc())
        )).scalars().all())

    async def _check_progress_operator(self, operator: User, student_id: int) -> None:
        """仅该学生的负责员工或管理层可更新进度。"""
        if operator.user_type == "MANAGER":
            return
        cust = (await self.db.execute(
            select(Customer).where(Customer.sys_user_id == student_id)
        )).scalars().first()
        if cust is None or cust.owner_employee_id != operator.id:
            raise ForbiddenError(message="仅该学生的负责员工或管理层可更新进度")

    async def update_progress(self, operator: User, student_id: int, data: ProgressUpdate) -> StudentApplicationProgress:
        if data.stage not in PROGRESS_STAGES:
            raise BusinessError(code=40002, message=f"无效阶段：{data.stage}，可选：{'/'.join(PROGRESS_STAGES)}")
        student = (await self.db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
        if student is None or student.user_type != "STUDENT":
            raise NotFoundError(message="学生不存在")
        await self._check_progress_operator(operator, student_id)

        row = (await self.db.execute(
            select(StudentApplicationProgress).where(
                StudentApplicationProgress.student_id == student_id,
                StudentApplicationProgress.stage == data.stage,
            )
        )).scalars().first()
        if row is None:
            row = StudentApplicationProgress(
                student_id=student_id, stage=data.stage, status=data.status,
                notes=data.notes, operator_id=operator.id,
                update_time=datetime.now(timezone.utc),
            )
            self.db.add(row)
        else:
            row.status = data.status
            row.notes = data.notes
            row.operator_id = operator.id
            row.update_time = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    # ── 生活支持 / 更多服务（本地静态） ──
    @staticmethod
    def life_faq() -> list[dict]:
        return LIFE_FAQS

    @staticmethod
    def more_services() -> list[dict]:
        return MORE_SERVICES
