export type Project = {
  id: number
  category: string
  title: string
  summary: string
  audience: string
  duration: string
  fee: string
  tag: string
  highlights: string[]
}

export const projects: Project[] = [
  {
    id: 1,
    category: '德国双元制',
    title: '中德精英人才共建计划',
    summary: '德国职业院校与企业双轨培养，毕业获得职业资格认证与就业机会。',
    audience: '18-35岁，高中及以上学历',
    duration: '2.5-3年',
    fee: '免学费 · 含带薪实习',
    tag: '就业导向',
    highlights: ['省属教育国企签约', '银行低息贷款支持', '国内外全程服务'],
  },
  {
    id: 2,
    category: '新加坡本硕',
    title: '新加坡国际本硕升学计划',
    summary: '定向培养联合办学，提供国际本科、硕士直升与短学制升学通道。',
    audience: '初中、高中、专科及本科毕业生',
    duration: '1-5年',
    fee: '25-31万元区间',
    tag: '热门',
    highlights: ['学制灵活', '学历可认证', '升学路径清晰'],
  },
  {
    id: 3,
    category: '国际留学',
    title: '全球院校直申计划',
    summary: '覆盖英美澳加新港日韩等主流目的地，提供院校匹配与申请全流程服务。',
    audience: '本科、硕士及博士申请者',
    duration: '按申请阶段确定',
    fee: '按服务方案确定',
    tag: '全球申请',
    highlights: ['数百所合作院校', '材料与签证指导', '全流程进度追踪'],
  },
  {
    id: 4,
    category: '国际研学',
    title: '国际名校研学项目',
    summary: '面向中小学生、高职高专及大学生的名校课堂、企业访学和文化浸润项目。',
    audience: '中小学生、高职高专及大学生',
    duration: '3-14天',
    fee: '按线路确定',
    tag: '寒假热门',
    highlights: ['分层培养方案', '专业带队管理', '研学成果记录'],
  },
  {
    id: 5,
    category: '新加坡本硕',
    title: '一年制专升本 / 本升硕',
    summary: '为专科和本科毕业生提供更短周期的海外学历提升路径。',
    audience: '国内专科及本科毕业生',
    duration: '1-1.5年',
    fee: '按院校方案确定',
    tag: '高性价比',
    highlights: ['短学制', '学历提升', '回国认证'],
  },
  {
    id: 6,
    category: '德国双元制',
    title: '德国护理与医疗健康方向',
    summary: '面向医疗健康紧缺方向，结合语言培训、职业实训与就业规划。',
    audience: '护理、医疗健康相关背景',
    duration: '2.5-3年',
    fee: '免学费 · 含补贴',
    tag: '紧缺职业',
    highlights: ['德语B1衔接', '企业带薪实训', '就业与长期发展'],
  },
]

export const events = [
  {
    id: 1,
    date: '10月22日',
    title: '新加坡国立大学本科申请解析会',
    format: '线上直播',
    speaker: '李老师',
    joined: 86,
    capacity: 200,
    status: '报名中',
  },
  {
    id: 2,
    date: '10月28日',
    title: '德国双元制职业教育开放日',
    format: '广州天河 · 线下',
    speaker: '张主任',
    joined: 42,
    capacity: 60,
    status: '名额紧张',
  },
  {
    id: 3,
    date: '11月05日',
    title: '留学文书写作工作坊',
    format: '线上 + 线下',
    speaker: 'Dr. Chen',
    joined: 118,
    capacity: 150,
    status: '报名中',
  },
  {
    id: 4,
    date: '09月12日',
    title: '2026秋季国际教育展',
    format: '广交会展馆',
    speaker: '30+ 参展院校',
    joined: 1280,
    capacity: 1500,
    status: '已结束',
  },
]

export const policies = [
  {
    country: '德国',
    date: '2026-09-28',
    title: '德国留学签证与双元制工签最新变化',
    summary: '双元制毕业生就业签证与实习薪资保障政策持续完善，申请材料要求更加规范化。',
  },
  {
    country: '新加坡',
    date: '2026-10-08',
    title: '新加坡公立大学申请时间轴',
    summary: 'NUS、NTU、SMU 等院校公布本科与硕士主要申请批次，建议提前一年规划。',
  },
  {
    country: '综合',
    date: '2026-10-12',
    title: '学历认证流程电子化说明',
    summary: '认证材料电子化提交逐步推行，办理周期和材料要求以官方最新公告为准。',
  },
]

export const faqs = [
  { q: '公司主要提供哪些教育服务？', a: '公司主营国际教育、智慧教育、素质教育和实体教育，核心业务包括德国双元制、新加坡国际本硕、国际留学和国际研学。' },
  { q: '没有登录可以浏览项目吗？', a: '可以。访客无需登录即可浏览公司、项目、课程、活动和政策；所有报名必须登录。' },
  { q: '报名后如何查看进度？', a: '登录后进入个人中心，可以查看报名记录、审核状态和相关消息通知。' },
  { q: '德国双元制项目的报名条件是什么？', a: '通常要求18-35岁、高中及以上学历，并具备一定的德语学习能力、动手能力和逻辑思维能力。' },
  { q: '新加坡项目有哪些升学路径？', a: '根据学历和年级不同，可匹配2+2、0.5/1+2、专升本、本升硕等不同路径。' },
  { q: '如何提交咨询？', a: '在公开端提交咨询表单，或直接与右下角智能客服沟通；已登录用户信息会自动带入。' },
  { q: '学生可以在线请假吗？', a: '可以。学生端行政服务支持提交请假、附件和查看审批进度。' },
  { q: '心理关怀服务的边界是什么？', a: '平台提供服务性情绪支持和风险识别，不提供医疗诊断，也不承诺退费、转学等重大决定。' },
]

export const customers = [

  { id: 7, name: '陈女士', phone: '136****7788', project: '新加坡国际本科', score: '符合', status: '跟进中', owner: '陈顾问', last: '今天' },
  { id: 8, name: '刘同学', phone: '135****1122', project: '德国双元制', score: '部分符合', status: '意向强烈', owner: '赵敏', last: '昨天' },
  { id: 9, name: '何先生', phone: '139****3344', project: '国际留学', score: '待确认', status: '已签约', owner: '孙浩', last: '2天前' },
  { id: 10, name: '林同学', phone: '137****5566', project: '国际研学', score: '符合', status: '已入学', owner: '李四', last: '4天前' },
  { id: 11, name: '周先生', phone: '138****7788', project: '新加坡硕士', score: '部分符合', status: '已流失', owner: '周琳', last: '1周前' },
  { id: 12, name: '高同学', phone: '133****9900', project: '德国双元制', score: '待确认', status: '新录入', owner: '陈顾问', last: '今天' },  { id: 1, name: '王女士', phone: '138****4455', project: '新加坡国际本科', score: '符合', status: '新录入', owner: '李四', last: '2小时前' },
  { id: 2, name: '李同学', phone: '139****2288', project: '新加坡硕士', score: '部分符合', status: '跟进中', owner: '李四', last: '昨天' },
  { id: 3, name: '王五', phone: '137****9900', project: '德国双元制', score: '部分符合', status: '意向强烈', owner: '赵敏', last: '3天前' },
  { id: 4, name: '陈同学', phone: '135****6611', project: '国际研学', score: '符合', status: '已签约', owner: '李四', last: '5天前' },
  { id: 5, name: '刘先生', phone: '136****3344', project: '待明确', score: '待确认', status: '已入学', owner: '孙浩', last: '1周前' },
  { id: 6, name: '周同学', phone: '133****7788', project: '语言培训', score: '不符合', status: '已流失', owner: '周琳', last: '2周前' },
]

export const reports = [
  { code: 'CA', name: '客户经营分析报告', cycle: '周报 / 月报', desc: '新增意向、转化路径、流失回流、项目画像与同比环比', tone: 'purple' },
  { code: 'DS', name: '员工日报汇总', cycle: '日报', desc: '按部门汇总团队进展、风险和提交情况', tone: 'green' },
  { code: 'WS', name: '员工周报汇总', cycle: '周报', desc: '团队工作变化、风险事项和周度对比', tone: 'blue' },
  { code: 'PW', name: '学生信息健康周报', cycle: '周报', desc: '整体心理态势、风险人数、周变化和节点标注', tone: 'coral' },
  { code: 'CW', name: '投诉处理周报', cycle: '周报', desc: '正式投诉量、处理率、首次响应与未解决情况', tone: 'amber' },
]

export const notifications = [
  { type: '审批结果', title: '请假申请已通过', time: '10分钟前', tone: 'green' },
  { type: '学业提醒', title: 'Data Structures 作业今晚截止', time: '1小时前', tone: 'amber' },
  { type: '待办提醒', title: '2名客户超过3天未跟进', time: '今天 09:20', tone: 'purple' },
]

export const studentTodos = [
  { title: '提交 Data Structures 作业', due: '今天 23:59', tone: 'coral' },
  { title: '补交护照扫描件', due: '10月16日', tone: 'amber' },
  { title: '确认期末考试时间', due: '10月22日前', tone: 'blue' },
]

