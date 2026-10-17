from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── 日报 ──────────────────────────────────────────────
class DailyReportCreate(BaseModel):
    report_date: date = Field(..., description="日报日期")
    content: str = Field(..., min_length=1, description="日报内容（结构化文本）")
    status: str = Field("submitted", description="draft=草稿 / submitted=正式提交")


class DailyReportDraftUpdate(BaseModel):
    content: str = Field(..., min_length=1, description="日报内容")


class LateApplyCreate(BaseModel):
    approver_id: int = Field(..., description="审批人（MANAGER）")


class LateReviewCreate(BaseModel):
    approval_id: int = Field(..., description="审批实例ID")
    action: str = Field(..., description="approved / rejected")
    comment: Optional[str] = None


class DailyReportOut(BaseModel):
    id: int
    employee_id: int
    report_date: date
    content: str
    status: str = "submitted"
    is_late: bool = False
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DailyReportSummaryItem(BaseModel):
    report_date: date
    submitted: int = 0


# ── 待办 ──────────────────────────────────────────────
class TodoCreate(BaseModel):
    todo_type: str = Field(..., max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    related_type: Optional[str] = Field(None, max_length=50)
    related_id: Optional[int] = None
    priority: str = Field("medium", max_length=10)
    due_time: Optional[datetime] = None


class TodoUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=20, description="pending/done/cancelled")
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=10)
    due_time: Optional[datetime] = None


class TodoOut(BaseModel):
    id: int
    employee_id: int
    todo_type: str
    title: str
    description: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    status: str
    priority: str
    due_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 组织架构 ──────────────────────────────────────────
class OrgNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    org_type: str
    leader_id: Optional[int] = None
    sort_order: int
    status: str
    children: list["OrgNode"] = []

    model_config = {"from_attributes": True}


OrgNode.model_rebuild()


# ── 成绩 ──────────────────────────────────────────────
class ScoreCreate(BaseModel):
    student_id: int = Field(..., description="学生 user id")
    course_name: str = Field(..., min_length=1, max_length=100)
    score: float = Field(..., ge=0, le=999.99)
    semester: Optional[str] = Field(None, max_length=50)


class ScoreOut(BaseModel):
    id: int
    student_id: int
    course_name: str
    score: float
    semester: Optional[str] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 代客申请留学生（走 approval convert） ─────────────
class ConvertApplyCreate(BaseModel):
    customer_id: int = Field(..., description="客户主表 ID")
    title: Optional[str] = Field(None, max_length=200, description="审批标题，缺省自动生成")
    approver_id: int = Field(..., description="经理 user id")


class ConvertApplyOut(BaseModel):
    approval_id: int
    biz_type: str
    biz_id: int
    status: str


# ── 学生行政服务审批（员工代处理/审批） ───────────────
class AdminServiceOut(BaseModel):
    id: int
    student_id: int
    service_type: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    status: str
    approver_id: Optional[int] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminServiceAction(BaseModel):
    action: str = Field(..., description="approve / reject")
    comment: Optional[str] = None


# ── 口述日报（AI 整理） ───────────────────────────────
class OralReportCreate(BaseModel):
    raw_text: str = Field(..., min_length=1, description="员工口述/随意记录原文")
    report_date: Optional[date] = Field(None, description="日报日期，缺省今天")


class OralReportOut(BaseModel):
    raw_text: str
    structured: str = Field(..., description="AI 整理后的结构化日报文本")
    report_date: date
    session_id: Optional[str] = None
    saved_report_id: Optional[int] = Field(None, description="如同时落库，返回日报 ID")


# ── CRM 客户录入（多格式：文字 + 已上传文件） ──────────
class CrmLeadCreate(BaseModel):
    """员工录入线索。

    多格式支持：
    - 纯文字：raw_text 必填
    - 文件（PDF/照片/Word/Excel）：先调 POST /api/v1/files/upload 拿 file_url，再传入 file_urls
    - 客户基础字段（phone/name/wechat 等）可选；若 phone 已有 customer，自动关联
    """
    raw_text: Optional[str] = Field(None, description="原始录入文本")
    file_urls: Optional[list[str]] = Field(None, description="已上传文件的 URL 列表")
    phone: Optional[str] = Field(None, max_length=20, description="手机号（有效性标准）")
    name: Optional[str] = Field(None, max_length=100)
    wechat: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    education: Optional[str] = Field(None, max_length=50)
    source_channel: Optional[str] = Field(None, max_length=32, description="来源渠道")
    background_info: Optional[str] = Field(None, description="背景信息")
    auto_assess: bool = Field(True, description="是否自动调 AI 研判")


class CrmLeadOut(BaseModel):
    lead_id: int
    customer_id: Optional[int] = None
    customer_existed: bool = Field(..., description="手机号是否已存在客户")
    assessment_id: Optional[int] = None
    status: str
    message: str


class CrmFollowUpCreate(BaseModel):
    customer_id: int
    follow_type: Optional[str] = Field(None, max_length=32)
    content: str = Field(..., min_length=1)
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None


class CrmFollowUpOut(BaseModel):
    id: int
    customer_id: int
    employee_id: int
    follow_type: Optional[str] = None
    content: Optional[str] = None
    next_action: Optional[str] = None
    next_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 指令式业务处理（AI 解析 + 二次确认） ────────────────
class CommandParseCreate(BaseModel):
    """员工用自然语言下达业务指令，AI 解析为结构化动作，返回 token。"""
    text: str = Field(..., min_length=1, description="自然语言指令，例如：给客户张三发条跟进记录：明天约面谈")


class CommandParsedAction(BaseModel):
    """AI 解析出的待执行动作。"""
    action_type: str = Field(..., description="follow_up.create / todo.create / score.record 等")
    params: dict = Field(default_factory=dict)
    summary: str = Field(..., description="员工可读的动作描述，用于二次确认展示")


class CommandParseOut(BaseModel):
    token: str = Field(..., description="待确认令牌，10 分钟有效")
    action: CommandParsedAction
    expires_in: int = 600


class CommandExecuteCreate(BaseModel):
    token: str = Field(..., description="来自 parse 接口的待确认令牌")
    confirm: bool = Field(True, description="true=执行；false=取消")


class CommandExecuteOut(BaseModel):
    executed: bool
    result: Optional[dict] = None
    message: str


# ── 客户状态机（6 态流转） ────────────────────────────
class CustomerStatusUpdate(BaseModel):
    status: str = Field(..., description="目标状态：新录入/跟进中/意向强烈/已签约/已入学/已流失")
    reason: Optional[str] = Field(None, description="变更原因")


class CustomerStatusOut(BaseModel):
    customer_id: int
    old_status: str
    new_status: str
    changed_at: Optional[datetime] = None


# ── 意向客户查询（数据隔离 + 筛选排序） ────────────────
class CustomerQueryItem(BaseModel):
    id: int
    phone: Optional[str] = None
    wechat: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    source_channel: Optional[str] = None
    status: str
    owner_employee_id: Optional[int] = None
    last_follow_at: Optional[datetime] = None
    assessment_score: Optional[int] = None
    recommended: Optional[dict] = Field(None, description="最新研判的推荐项目与理由（recommended_json）")
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 心理关怀待办标记 ─────────────────────────────────
class PsychAlertHandle(BaseModel):
    action: str = Field(..., description="处理动作：communicated/referred/resolved")
    note: Optional[str] = Field(None, description="处理备注")


class PsychAlertOut(BaseModel):
    id: int
    student_id: int
    trigger_reason: str
    risk_level: str
    status: str
    teacher_id: Optional[int] = None
    handled_action: Optional[str] = None
    handled_at: Optional[datetime] = None
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 日报批示（MANAGER） ─────────────────────────────
class AnnotationCreate(BaseModel):
    content: str = Field(..., min_length=1, description="批示内容")


class AnnotationOut(BaseModel):
    id: int
    report_id: int
    manager_id: int
    content: str
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 客户再分配（MANAGER） ────────────────────────────
class ReassignCreate(BaseModel):
    from_employee_id: int = Field(..., description="原归属员工")
    to_employee_id: int = Field(..., description="新归属员工")
    customer_ids: Optional[list[int]] = Field(None, description="指定客户ID列表，不传则全部转移")


# ── 个人信息 ────────────────────────────────────────
class ProfileUpdate(BaseModel):
    real_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    contact_info: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str = Field(..., min_length=1, description="旧密码（验证用）")
    new_password: str = Field(..., min_length=6, max_length=64, description="新密码（至少6位）")


# ── 企业智能助手 Agent（权限感知） ──────────────────────
class AgentChatCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID；不传或 new 表示新会话")


class AgentChatOut(BaseModel):
    reply: str
    session_id: str
    source: str = Field(..., description="dify=AI网关 / fallback=本地降级（AI不可用）")


# ── 新人指引 ──────────────────────────────────────────
class GuideItemOut(BaseModel):
    q: str
    a: str


class GuideSectionOut(BaseModel):
    key: str
    title: str
    summary: str
    items: list[GuideItemOut]


class GuideAskCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="提问内容")
    session_id: Optional[str] = None


class GuideAskOut(BaseModel):
    answer: str
    source: str = Field(..., description="dify=AI RAG / local=本地静态指引匹配")
    session_id: Optional[str] = None


# ── 提醒聚合（登录拉取） ───────────────────────────────
class RemindersOut(BaseModel):
    todos_pending: int = Field(0, description="未完成待办数")
    follow_ups_due: int = Field(0, description="今日应跟进客户数（next_date<=今天）")
    admin_services_pending: int = Field(0, description="待我审批的学生行政服务单数")
    psych_alerts_pending: int = Field(0, description="未处理心理预警数")
    approvals_pending: Optional[int] = Field(None, description="待我审批的审批单数（仅 MANAGER 返回）")


# ── 组织架构成员（v6.6.0：同事查询 + 电话脱敏） ──────────
class OrgMemberItem(BaseModel):
    user_id: int
    real_name: str
    user_type: str
    employee_role: Optional[str] = None
    department: Optional[str] = None
    phone_masked: Optional[str] = Field(None, description="脱敏电话，如 138****5678")


class PhoneRevealOut(BaseModel):
    user_id: int
    real_name: str
    phone: Optional[str] = Field(None, description="完整电话（敏感操作，已写操作日志）")


# ── 操作日志查询（v6.6.0，Phase 1.3 管理层端） ──────────
class OperationLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    module: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[dict] = None
    created_at: Optional[datetime] = None


# ── 用户管理（v6.7.0，Phase 1.3 管理层端） ──────────────
class ManagerUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名（唯一）")
    password: str = Field(..., min_length=6, max_length=100, description="初始密码（至少6位）")
    real_name: str = Field(..., min_length=2, max_length=50, description="真实姓名")
    user_type: str = Field(..., pattern="^(EMPLOYEE|MANAGER)$", description="用户类型（管理层仅可创建这两种）")
    phone: Optional[str] = Field(None, max_length=20, description="手机号（唯一）")
    employee_role: Optional[str] = Field(None, max_length=50, description="岗位角色")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    permissions: Optional[list[str]] = Field(None, description="额外权限列表（MANAGER 的 permissions JSON）")


class ManagerUserStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(正常|禁用)$", description="目标状态")


class ManagerUserPermissionsUpdate(BaseModel):
    permissions: list[str] = Field(..., description="权限列表（覆盖式写入 permissions JSON，传 [] 清空）")


class ManagerUserOut(BaseModel):
    id: int
    username: str
    real_name: str
    user_type: str
    phone: Optional[str] = None
    employee_role: Optional[str] = None
    department: Optional[str] = None
    permissions: Optional[list[str]] = None
    status: str
    create_time: Optional[datetime] = None

    model_config = {"from_attributes": True}
