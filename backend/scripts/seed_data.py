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

# 待补全线索 / CRM 线索的拟真文案（替换原 wx_{i}、"原始信息_{i}" 等机器占位符）
WECHAT_IDS = [
    "wxid_zhangwei88", "wxid_wangfang2026", "wxid_lina_de", "wxid_liuyang88",
    "wxid_chenjie_2025", "wxid_yangxiuying", "wxid_huangyong66", "wxid_zhaomin_gz",
    "wxid_zhoujie2026", "wxid_wuli_nj", "wxid_xuqiang_sz", "wxid_sunyan_dg",
    "wxid_huming2026", "wxid_zhuhong88", "wxid_gaofeng_gz",
]
PENDING_LEAD_SCENES = [
    "微信咨询德国双元制护理项目，暂未留手机号",
    "公众号留言想了解澳洲本科预科，未填意向城市",
    "抖音私信咨询雅思课程费用",
    "老学员推荐添加微信，想了解高中留学方案",
    "线下展会扫码留资，意向国家待确认",
    "官网弹窗咨询加拿大高中，未留邮箱",
    "小红书私信咨询日本语言学校",
    "电话咨询英国硕士申请，未留微信号",
    "微信社群咨询德国双元制，需顾问对接",
    "校园讲座留资，想了解新加坡本科",
]
CRM_RAW_INPUTS = [
    "官网表单：想了解德国双元制护理，本科在读，计划2027年入学",
    "客服转交：咨询雅思强化班开课时间与费用",
    "员工录入：朋友介绍，想了解澳洲本科预科申请条件",
    "官网表单：高中毕业，咨询加拿大大专留学方案",
    "客服转交：想了解留学签证资金证明要求",
    "员工录入：展会留资，意向英国硕士，需顾问回访",
    "官网表单：家长咨询德国双元制项目就业前景",
    "客服转交：咨询日本语言学校入学时间与住宿",
    "员工录入：想转学新加坡本科，咨询学分转换",
    "官网表单：想了解香港硕士，需评估本科成绩",
]
CRM_BACKGROUNDS = [
    "本科在读，GPA 3.2，暂无雅思成绩，家庭预算约一年30万",
    "高中应届毕业，均分85，计划次年春季入学",
    "大专毕业两年，有护理工作经验，意向德国双元制",
    "本科毕业，雅思6.0，希望申请澳洲八大",
    "高一在读，家长陪同咨询，预算充足",
    "本科在读，有科研经历，目标英国G5",
    "职高毕业，德语零基础，意向赴德培训",
    "本科毕业一年，跨专业申请，需补充先修课",
    "高三在读，计划高考后出国，关注新加坡",
    "本科在读，想申请香港授课型硕士，需奖学金信息",
]

# 业务文案池：统一替换 seed 中 f"xxx_{i}" 形式的机器占位符，避免演示数据看起来像假数据
CUSTOMER_OVERVIEWS = [
    "本科在读，意向德国双元制护理，预算充足，语言成绩待补",
    "高中毕业，想申请澳洲本科预科，关注升学率",
    "大专护理专业，希望赴德带薪培训，德语零基础",
    "本科毕业，目标英国硕士，已考雅思 6.0",
    "高一在读，家长陪同咨询，关注寄宿与安全",
    "本科在读，想申请香港授课型硕士，需奖学金",
    "职高毕业，倾向日本语言学校过渡升学",
    "本科毕业一年，跨专业申请加拿大研究生文凭",
    "高三在读，计划高考后赴新加坡读本科",
    "研究生在读，咨询海外博士申请与套磁",
]
FOLLOW_UP_ADVICES = [
    "建议 3 天内电话回访，确认入学时间与家庭预算",
    "推送德国双元制项目手册，并约定本周面谈",
    "提醒客户补交语言成绩，跟进材料准备进度",
    "邀约参加周六线下说明会，现场答疑",
    "先确认目标国家与专业方向，再出具选校方案",
    "跟进家长顾虑点（费用/安全/升学率）",
    "发送往届学员案例，增强意向",
    "确认签证资金证明准备情况",
    "推荐雅思基础班，先解决语言门槛",
    "建议先做一次免费背景评估",
]
FOLLOW_UP_CONTENTS = [
    "电话沟通：客户确认意向专业为护理，需补充语言成绩",
    "微信沟通：已发送项目介绍，客户表示会与家人商量",
    "面谈：家长关注费用与住宿，已给出费用清单",
    "邮件发送：选校方案与申请时间表，等待回复",
    "电话回访：客户仍在比较德国与日本方向",
    "微信沟通：客户询问报名截止时间与名额",
    "面谈：确认委托意向，进入材料准备阶段",
    "电话沟通：客户反馈雅思首考 5.5，需再刷分",
    "微信沟通：家长要求提供往届升学数据",
    "邮件发送：签证材料清单与时间节点",
]
FOLLOW_UP_NEXT_ACTIONS = [
    "发送项目手册并预约下周面谈",
    "一周后电话回访确认决策进展",
    "协助客户完成背景评估问卷",
    "邀约参加本周六线下说明会",
    "提供费用明细与分期方案",
    "跟进语言班报名与开课时间",
    "整理往届录取案例发送客户",
    "提醒补充学历与成绩单材料",
    "安排顾问与家长线上面谈",
    "确认签约时间并准备合同",
]
FAQ_QUESTIONS = [
    "德国双元制护理项目需要什么条件？",
    "雅思基础班和强化班有什么区别？",
    "留学申请一般需要准备哪些材料？",
    "签约后多久可以拿到院校 offer？",
    "签证被拒签了还能再申请吗？",
    "课程费用可以分期付款吗？",
    "可以先去语言班再申请学校吗？",
    "你们提供境外住宿安排服务吗？",
    "申请失败的退款政策是怎样的？",
    "周末有线下说明会可以参加吗？",
]
FAQ_ANSWERS = [
    "一般要求高中及以上学历、德语 B1 或通过入学语言测试，具体以项目要求为准。",
    "基础班侧重语法与词汇打基础，强化班侧重题型训练与冲刺提分，可按当前水平选择。",
    "通常需要学历证明、成绩单、语言成绩、护照及资金证明，顾问会提供完整清单。",
    "材料齐全且院校审理顺利的情况下，一般 4-8 周可收到 offer。",
    "可以，需根据拒签原因补充材料后重新递交，顾问会协助复盘。",
    "支持分期付款，具体期数可与顾问沟通确认。",
    "可以，语言班结束后可衔接正式课程申请。",
    "提供接机、住宿与落地指导等境外服务，详情咨询顾问。",
    "未获录取按合同约定退还相应服务费用，具体以签约条款为准。",
    "每周六下午在广州总部有线下说明会，可在线预约名额。",
]
FAQ_KEYWORDS = [
    "双元制,护理,条件", "雅思,基础班,强化班", "留学,材料,清单", "offer,周期", "拒签,再申请",
    "费用,分期", "语言班,衔接", "住宿,接机", "退款,政策", "说明会,预约",
]
SESSION_TITLES = [
    "咨询德国双元制护理项目", "询问雅思课程与开课时间", "了解澳洲本科预科申请条件",
    "咨询加拿大高中留学费用", "询问留学签证材料", "了解英国硕士申请流程",
    "咨询日本语言学校入学时间", "询问新加坡本科申请要求", "了解香港硕士奖学金",
    "咨询转学与学分转换",
]
CHAT_MESSAGES = [
    "你好，我想了解一下德国双元制护理项目",
    "同学你好，这个项目对语言有什么要求？",
    "我目前是大专护理专业，可以申请吗？",
    "可以的，请问你有没有德语基础？",
    "暂时没有，需要先读语言班吗？",
    "对的，建议先完成 B1 语言课程再进入项目。",
    "课程费用大概是多少？可以分期吗？",
    "支持分期付款，具体期数可以帮你确认。",
    "好的，那我先了解一下，谢谢。",
    "不客气，有需要随时联系我。",
]
EVENT_NAMES = [
    "德国双元制护理项目说明会", "雅思提分公开课", "澳洲八大申请解析讲座",
    "加拿大高中留学分享会", "英国硕士申请工作坊", "日本留学政策说明会",
    "新加坡本科招生说明会", "香港硕士申请经验分享", "暑期背景提升项目沙龙",
    "行前准备与签证指导开放日",
]
EVENT_DESCRIPTIONS = [
    "现场讲解双元制护理项目的申请条件、费用与就业前景，可一对一咨询。",
    "针对听说读写的提分技巧讲解，含现场测评与学习规划建议。",
    "深度解析澳洲八大录取偏好与文书准备要点。",
    "邀请往届家长分享加拿大高中就读与寄宿体验。",
    "手把手指导英国硕士文书与套磁邮件写作。",
    "讲解最新日本留学政策、语言学校选择与升学路径。",
    "介绍新加坡公立与私立院校的申请条件与时间线。",
    "邀请在读学长分享香港硕士申请与就读经验。",
    "介绍暑期科研、竞赛与志愿者项目的参与方式。",
    "签证材料准备、行前清单与境外生活指导。",
]
COURSE_DESCRIPTIONS = [
    "面向雅思 5 分左右学员，夯实语法与核心词汇。",
    "针对冲刺 6.5+ 的学员，强化题型技巧与模考训练。",
    "托福零基础入门，听说读写全科打基础。",
    "托福 80 分以上学员的提分强化课程。",
    "SAT 数学与阅读基础训练，适合高一高二学生。",
    "A-Level 数学核心考点精讲与真题演练。",
    "A-Level 物理实验与计算题专项突破。",
    "AP 微积分 AB/BC 考点梳理与真题训练。",
    "AP 宏观经济与微观经济考点精讲。",
    "IB 全科辅导，按学科定制学习计划。",
    "外教口语小班，提升表达流利度与发音。",
    "学术写作规范训练，覆盖论文结构与引用。",
    "从选校到文书的全流程留学规划指导。",
    "科研、竞赛与实习等背景提升项目策划。",
    "模拟面试与常见问题应答技巧训练。",
]
DAILY_REPORT_CONTENTS = [
    "今日回访客户 6 位，新增意向客户 2 位，跟进德国双元制项目 1 单。",
    "完成 3 位客户的材料初审，协助 1 位客户提交院校申请。",
    "接待到访家长 2 组，讲解双元制护理项目并发送资料。",
    "电话跟进已签约客户 4 位，确认语言班开课安排。",
    "整理本周线索 12 条，其中 3 条转入正式跟进。",
    "协助 2 位学生完成签证材料准备与预约。",
    "参加部门例会，梳理下周招生目标与分工。",
    "处理客户投诉 1 起，已与教务沟通并回复客户。",
    "跟进雅思班报名 5 人，其中 3 人已缴费。",
    "汇总本周成交数据并更新 CRM 跟进记录。",
]
TODO_TITLES = [
    "回访德国双元制意向客户", "整理本周新增线索", "跟进雅思班报名缴费",
    "提交日报补报申请", "审核学生请假申请", "准备周六说明会物料",
    "联系院校确认 offer 进度", "整理签证材料清单", "跟进客户投诉处理结果",
    "更新客户跟进记录",
]
LEAVE_REASONS = [
    "身体不适，需就医休息两天", "家中有事，需返乡处理", "参加亲属婚礼，请假三天",
    "感冒发热，医生建议休息", "需参加校外语言考试", "家庭聚会，申请事假一天",
    "脚部受伤，需复查治疗", "参加重要面试，请假半天", "陪伴家人体检，申请事假",
    "需要办理签证材料公证，请假一天",
]
PSYCH_ALERT_REASONS = [
    "连续三次评估情绪低落，建议辅导员介入", "自述睡眠质量差、焦虑明显",
    "近期缺课较多且情绪波动较大", "评估中出现明显压力表述，需关注",
    "与同学发生冲突后情绪低落", "临近考试压力上升，情绪评分持续下滑",
    "主动求助表达孤独感，建议谈心", "饮食与作息紊乱，情绪评分偏低",
    "家长反馈学生近期情绪异常", "连续两周情绪标签为焦虑",
]
TICKET_CONTENTS = [
    "住宿安排与承诺不一致", "课程顾问回复不及时", "语言班课程质量与宣传不符",
    "申请材料交接出现遗漏", "退费流程说明不清晰", "签证材料准备指导不够细致",
    "线下活动组织混乱", "顾问更换频繁导致沟通断层", "课后服务跟进不到位",
    "费用明细不透明",
]
TICKET_DETAILS = [
    "客户反馈签约后实际住宿与顾问介绍的房型不符，希望协调更换。",
    "客户多次微信咨询未获及时回复，希望明确服务响应时间。",
    "客户认为课程内容与宣传差异较大，要求说明与调整方案。",
    "客户的材料在内部交接时遗漏一份，导致申请延误，要求解释。",
    "客户申请退费时不清楚所需材料与周期，希望提供书面流程。",
    "客户对签证材料清单理解困难，希望安排专人一对一指导。",
    "客户参加线下活动时现场秩序混乱，体验不佳。",
    "客户中途更换顾问，历史沟通记录未同步，影响服务连续性。",
    "客户反映课后作业批改与反馈缺失，希望补齐。",
    "客户希望看到完整的费用构成明细，避免隐性收费。",
]
ACADEMIC_TITLES = [
    "德语 B1 阶段测试", "雅思模拟考试（第 3 次）", "护理基础课程作业提交",
    "选课：德语口语强化", "期末成绩公布", "线上课程出勤确认",
    "实践报告提交", "专业词汇测评", "小组作业汇报", "学籍信息核对",
]
REPORT_TITLES = [
    "每日经营情况汇总", "本周客户转化分析", "月度招生数据报告",
    "学生心理健康周报", "投诉与满意度分析", "线索来源渠道分析",
    "员工日报汇总", "活动报名与到场分析", "课程报名与续费分析", "意向客户结构分析",
]
APPROVAL_TITLES = [
    "学生请假申请（事假）", "学生请假申请（病假）", "客户转化申请",
    "日报补报申请", "学生休学申请", "学生复学申请",
    "投诉处理结果确认", "转班申请", "客户线索转移申请", "报销单据审批",
]
APPROVAL_COMMENTS = [
    "情况属实，同意。", "已核实材料，批准。", "同意，请按流程办理。",
    "材料不全，请补充后重新提交。", "不符合规定，不予批准。",
    "同意，注意后续跟进。", "已与当事人确认，批准。", "暂缓，需上级复核。",
    "同意，请留存记录。", "同意，请及时归档。",
]
NOTIFICATION_TITLES = [
    "有一条待审批申请待处理", "你负责的客户状态已更新", "今日有客户待跟进",
    "本周日报汇总已生成", "学生心理预警需关注", "你有一条待办即将到期",
    "活动报名人数已达到上限", "新增一条客户线索", "成绩录入已确认", "系统维护通知",
]
NOTIFICATION_CONTENTS = [
    "有一条申请已进入你的审批队列，请及时处理。",
    "你负责的客户状态已变更为「意向强烈」，请跟进。",
    "请到「客户经营」按最后跟进时间查看待跟进明细。",
    "本周经营数据已汇总，可在「智能汇总」中查看。",
    "有学生心理预警等级升高，请及时关注并介入。",
    "该待办将于今日到期，请尽快处理。",
    "线下活动报名已满员，请确认后续安排。",
    "系统已自动分配一条新线索到你的名下。",
    "学生成绩已录入并核对完成，可查看明细。",
    "系统将于今晚 23:00 进行例行维护，请提前保存工作。",
]


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
                name=NAMES[i % len(NAMES)],
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
                wechat=WECHAT_IDS[i % len(WECHAT_IDS)],
                name=NAMES[i % len(NAMES)],
                raw_info=PENDING_LEAD_SCENES[i % len(PENDING_LEAD_SCENES)],
                status="pending",
            ))

        # ── M1: CRM 线索 ──
        for i in range(110):
            lead = CrmLead(
                customer_id=random.choice(customer_ids),
                source=random.choice(["website", "cs", "employee"]),
                raw_input=CRM_RAW_INPUTS[i % len(CRM_RAW_INPUTS)],
                background_info=CRM_BACKGROUNDS[i % len(CRM_BACKGROUNDS)],
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
                overview=CUSTOMER_OVERVIEWS[i % len(CUSTOMER_OVERVIEWS)],
                follow_up_advice=FOLLOW_UP_ADVICES[i % len(FOLLOW_UP_ADVICES)],
                prompt_version="JUDGE-v1.0",
                employee_id=random.choice(employee_ids),
            ))

        for i in range(120):
            session.add(CrmFollowUp(
                customer_id=random.choice(customer_ids),
                employee_id=random.choice(employee_ids),
                follow_type=random.choice(["电话", "微信", "面谈", "邮件"]),
                content=FOLLOW_UP_CONTENTS[i % len(FOLLOW_UP_CONTENTS)],
                next_action=FOLLOW_UP_NEXT_ACTIONS[i % len(FOLLOW_UP_NEXT_ACTIONS)],
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
                content=FOLLOW_UP_CONTENTS[(i + 5) % len(FOLLOW_UP_CONTENTS)],
                next_action="回访确认最新意向",
                next_date=datetime.now() - timedelta(days=i),
            ))

        # ── M2: CS ──
        for i in range(105):
            session.add(CsFaq(
                category=random.choice(["课程", "费用", "留学", "活动", "生活"]),
                question=FAQ_QUESTIONS[i % len(FAQ_QUESTIONS)],
                answer=FAQ_ANSWERS[i % len(FAQ_ANSWERS)],
                keywords=FAQ_KEYWORDS[i % len(FAQ_KEYWORDS)],
                sort_order=i,
            ))

        sessions = []
        for i in range(110):
            s = CsChatSession(
                user_id=random.choice(prospect_ids + student_ids),
                customer_id=random.choice(customer_ids) if random.random() > 0.3 else None,
                agent_type=random.choice(["CUSTOMER", "STUDENT", "EMPLOYEE"]),
                status=random.choice(["active", "closed"]),
                title=SESSION_TITLES[i % len(SESSION_TITLES)],
            )
            session.add(s)
            sessions.append(s)
        await session.flush()

        for i in range(200):
            session.add(CsChatMessage(
                session_id=random.choice([s.id for s in sessions]),
                role=random.choice(["user", "assistant"]),
                content=CHAT_MESSAGES[i % len(CHAT_MESSAGES)],
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
                event_name=EVENT_NAMES[i % len(EVENT_NAMES)],
                event_type=random.choice(["讲座", "开放日", "说明会", "沙龙"]),
                start_time=datetime.now() + timedelta(days=random.randint(-30, 60)),
                end_time=datetime.now() + timedelta(days=random.randint(1, 90)),
                location=random.choice(LOCATIONS),
                max_participants=random.choice([30, 50, 100, 200]),
                current_participants=random.randint(0, 50),
                description=EVENT_DESCRIPTIONS[i % len(EVENT_DESCRIPTIONS)],
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
                description=COURSE_DESCRIPTIONS[i % len(COURSE_DESCRIPTIONS)],
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
                content=DAILY_REPORT_CONTENTS[i % len(DAILY_REPORT_CONTENTS)],
            ))

        for i in range(100):
            session.add(EmployeeTodo(
                employee_id=random.choice(employee_ids + manager_ids),
                todo_type=random.choice(["follow_up", "approval", "review", "meeting"]),
                title=TODO_TITLES[i % len(TODO_TITLES)],
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
                reason=LEAVE_REASONS[i % len(LEAVE_REASONS)],
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
                trigger_reason=PSYCH_ALERT_REASONS[i % len(PSYCH_ALERT_REASONS)],
                status=random.choice(["未处理", "处理中", "已关闭"]),
                teacher_id=random.choice(employee_ids + manager_ids),
            ))

        tickets = []
        for i in range(100):
            t = StudentFeedbackTicket(
                student_id=random.choice(student_ids),
                content=TICKET_CONTENTS[i % len(TICKET_CONTENTS)],
                detail=TICKET_DETAILS[i % len(TICKET_DETAILS)],
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
                title=ACADEMIC_TITLES[i % len(ACADEMIC_TITLES)],
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
                report_title=REPORT_TITLES[i % len(REPORT_TITLES)],
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
                payload={"seq": i, "biz_id": random.randint(1000, 9999)},
                status=random.choice(["pending", "consumed", "failed"]),
            ))

        # ── 审批（双表设计） ──
        approval_instances = []
        for i in range(100):
            inst = ApprovalInstance(
                biz_type=random.choice(["leave", "convert", "late_report", "complaint"]),
                biz_id=random.randint(1, 500),
                title=APPROVAL_TITLES[i % len(APPROVAL_TITLES)],
                initiator_id=random.choice(employee_ids + student_ids),
                status=random.choice(["pending", "approved", "rejected"]),
                current_step=1,
                total_steps=1,
            )
            session.add(inst)
            approval_instances.append(inst)
        await session.flush()

        # 演示需要：核心管理层账号（固定 13810000004）名下必须分到待审批任务，
        # 否则 MANAGER 端「待我审批」(/approvals/pending) 恒空（审批按 approver_id 过滤）
        core_manager = next((u for u in users if u.username == "13810000004"), None)
        pending_seq = 0
        for inst in approval_instances:
            approver_id = random.choice(manager_ids)
            if inst.status == "pending":
                pending_seq += 1
                if core_manager and pending_seq % 3 == 0:
                    approver_id = core_manager.id
            session.add(ApprovalTask(
                instance_id=inst.id,
                approver_id=approver_id,
                seq_no=1,
                action=random.choice(["approved", "rejected"]) if inst.status != "pending" else None,
                comment=APPROVAL_COMMENTS[inst.id % len(APPROVAL_COMMENTS)],
                status="completed" if inst.status != "pending" else "pending",
            ))

        for i in range(100):
            session.add(SysNotification(
                user_id=random.choice([u.id for u in users]),
                type=random.choice(["approval", "todo", "academic", "psych_alert", "status", "system"]),
                title=NOTIFICATION_TITLES[i % len(NOTIFICATION_TITLES)],
                content=NOTIFICATION_CONTENTS[i % len(NOTIFICATION_CONTENTS)],
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
