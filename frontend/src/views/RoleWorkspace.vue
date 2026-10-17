<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRight,
  Delete,
  Download,
  Edit,
  Plus,
  Refresh,
  Search,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatCard from '../components/StatCard.vue'
import SectionTitle from '../components/SectionTitle.vue'
import { customers, events, notifications, projects, studentTodos } from '../data/mock'
import { REPORT_TYPES, typeName } from '../config/reports'
import { platformApi } from '../api/platform'

const route = useRoute()
const router = useRouter()
const role = computed(() => String(route.params.role || 'PROSPECT').toUpperCase())
const section = computed(() => String(route.params.section || 'home'))
const keyword = ref('')
const customerDialog = ref(false)
const leaveDialog = ref(false)
const psychScore = ref(72)
const customerForm = reactive({ name: '', phone: '', gender: '', age: '', education: '', project: '新加坡本硕', note: '' })
const leaveForm = reactive({ type: '事假', start: '', end: '', reason: '' })
const ticketForm = reactive({ title: '', detail: '', formal: false })
const reportForm = reactive({ date: new Date().toISOString().slice(0, 10), content: '' })
const convertForm = reactive({ customerId: 1, project: '新加坡国际本硕升学计划', title: '', approverId: 4 })
const submittedConversionIds = new Set<number>()
const activeCustomer = ref<any>(null)
const customerRows = ref<any[]>(customers)
const notificationRows = ref<any[]>(notifications)
const reminders = ref<any>({})
const approvalRows = ref<any[]>([])
const studentProfile = ref<any>({})
const studentTickets = ref<any[]>([])
const lifeFaqRows = ref<any[]>([])
const moreServiceRows = ref<any[]>([])

// ── M5 智能报告状态（M5-05.1~05.9） ──────────────────────────
const reportFilterType = ref('')
const reportPage = ref(1)
const reportPageSize = 10
const reportTotal = ref(0)
const reportList = ref<any[]>([])
const reportLoading = ref(false)
const reportError = ref('')
const reportGenerating = ref('')
const selectedReport = ref<any>(null)
const detailLoading = ref(false)
const drill = ref<Record<string, any[]>>({ customers: [], psychCases: [], specialCases: [] })
const drillLoading = ref('')

function itemsOf(value: any): any[] {
  if (Array.isArray(value)) return value
  return value?.items || []
}

onMounted(async () => {
  try {
    const requests: Promise<any>[] = [platformApi.notifications()]
    // M5-05.9：员工端不再请求 /reports（该组接口仅 MANAGER/ADMIN，员工调用必 403）
    if (role.value === 'EMPLOYEE' || role.value === 'MANAGER') {
      requests.push(platformApi.employeeCustomers(), platformApi.employeeReminders())
    }
    if (role.value === 'MANAGER') {
      requests.push(platformApi.reports.list({ page: 1, page_size: reportPageSize }))
    }
    const results = await Promise.all(requests)
    notificationRows.value = itemsOf(results[0])
    if (results.length > 1) {
      customerRows.value = itemsOf(results[1])
      reminders.value = results[2] || {}
      if (role.value === 'MANAGER') {
        const page: any = results[3] || {}
        reportList.value = page.items || []
        reportTotal.value = page.total || 0
      }
    }
  } catch {
    // Keep the initial test set when a module endpoint is not available.
  }
})

// ── M5 智能报告：列表 / 生成 / 详情 / 下钻 / 导出（M5-05.1~05.8） ──────────
async function loadReports() {
  reportLoading.value = true
  reportError.value = ''
  try {
    const page: any = await platformApi.reports.list({
      report_type: reportFilterType.value || undefined,
      page: reportPage.value,
      page_size: reportPageSize,
    })
    reportList.value = page?.items || []
    reportTotal.value = page?.total || 0
  } catch (error: any) {
    const message = String(error?.message || '')
    if (message.includes('无权限')) reportError.value = '无权限查看智能报告（仅 MANAGER/ADMIN）'
    else if (message.includes('不存在')) reportError.value = '报告接口未开放'
    else reportError.value = message || '报告列表加载失败，请稍后重试'
    reportList.value = []
    reportTotal.value = 0
  } finally {
    reportLoading.value = false
  }
}

function generateReport(type: string) {
  confirmWrite('确认生成「' + typeName(type) + '」吗？重复生成同类型同周期会保留历史版本。', async () => {
    reportGenerating.value = type
    try {
      await platformApi.reports.generate({ report_type: type })
      notifySuccess('报告已生成')
      reportPage.value = 1
      await loadReports()
    } catch (error: any) {
      // 拦截器已提示业务错误；这里补状态呈现
      reportError.value = String(error?.message || '生成失败，请稍后重试')
    } finally {
      reportGenerating.value = ''
    }
  })
}

async function openReport(row: any) {
  detailLoading.value = true
  try {
    selectedReport.value = await platformApi.reports.get(row.id)
    drill.value = { customers: [], psychCases: [], specialCases: [] }
  } catch (error: any) {
    ElMessage.error(String(error?.message || '报告详情加载失败'))
  } finally {
    detailLoading.value = false
  }
}

function backToReportList() {
  selectedReport.value = null
}

async function loadDrill(kind: 'customers' | 'psychCases' | 'specialCases') {
  if (!selectedReport.value) return
  drillLoading.value = kind
  try {
    const data: any = await platformApi.reports[kind](selectedReport.value.id)
    drill.value[kind] = itemsOf(data)
  } catch (error: any) {
    drill.value[kind] = []
    ElMessage.warning(String(error?.message || '下钻数据不可用'))
  } finally {
    drillLoading.value = ''
  }
}

async function downloadReportPdf() {
  if (!selectedReport.value) return
  try {
    const blob: any = await platformApi.reports.download(selectedReport.value.id)
    const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'report_' + selectedReport.value.id + '.pdf'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    ElMessage.error(String(error?.message || '导出失败：报告可能无内容'))
  }
}

/** AI 文字来源文案（M5-10.6 差异字段 ai_source：model / mock / unavailable） */
function aiSourceText(content: any): string {
  if (!content || content.ai_status !== 'available') return '不可用，仅展示确定性指标'
  if (content.ai_source === 'model') return '可用（共用模型网关）'
  if (content.ai_source === 'mock') return '可用（模拟数据）'
  return '可用'
}

/** 展开层 metrics 为可渲染的键值行（一层嵌套展平） */
function metricRows(metrics: any): { key: string; value: any }[] {
  if (!metrics || typeof metrics !== 'object') return []
  const rows: { key: string; value: any }[] = []
  for (const [key, value] of Object.entries(metrics)) {
    if (value !== null && typeof value === 'object') {
      for (const [k2, v2] of Object.entries(value as any)) rows.push({ key: key + ' · ' + k2, value: v2 })
    } else {
      rows.push({ key, value })
    }
  }
  return rows
}
function notifySuccess(message: string) {
  ElMessage['success'](message)
}
function notifyInfo(message: string) {
  ElMessage['info'](message)
}

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    home: role.value === 'STUDENT' ? '学生工作台' : role.value === 'EMPLOYEE' ? '员工工作台' : role.value === 'MANAGER' ? '经营看板' : '我的首页',
    customers: '客户经营', convert: '学生业务综管', reports: role.value === 'MANAGER' ? '智能汇总' : '日报管理',
    scores: '成绩录入', org: '组织与指引', todos: '待办与消息', profile: '个人信息',
    admin: '行政服务', psych: '心理关怀', feedback: '售后反馈', academic: '学业考务',
    progress: '进度追踪', life: '生活支持', more: '更多服务', approvals: '审批中心',
    employees: '员工管理', permissions: '权限配置', logs: '消息与日志', courses: '课程与项目',
    events: '活动报名', consult: '我的咨询',
  }
  return map[section.value] || '工作空间'
})

const filteredCustomers = computed(() => customerRows.value.filter((item: any) =>
  !keyword.value || item.name.includes(keyword.value) || item.phone.includes(keyword.value) || item.project.includes(keyword.value),
))

const employeeMenu = computed(() => [
  { label: '客户录入', icon: Plus, action: () => { customerDialog.value = true } },
  { label: '我的客户', icon: UserFilled, action: () => router.push('/app/employee/customers') },
  { label: '口述日报', icon: Edit, action: () => router.push('/app/employee/reports') },
  { label: '组织架构', icon: Search, action: () => router.push('/app/employee/org') },
])

function confirmWrite(message: string, done: () => void) {
  ElMessageBox.confirm(message, '二次确认', { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' })
    .then(done)
    .catch(() => undefined)
}

async function submitConvertApply() {
  const customerId = Number(convertForm.customerId)
  if (submittedConversionIds.has(customerId)) {
    ElMessage.warning('该客户已有待审批的留学生转化申请')
    return
  }
  try {
    const pending = await platformApi.approvals.pending({ biz_type: 'convert' })
    const existing = itemsOf(pending).find((item: any) => Number(item.biz_id) === customerId && item.status === 'pending')
    if (existing) {
      ElMessage.warning('该客户已有待审批的留学生转化申请')
      submittedConversionIds.add(customerId)
      return
    }
  } catch {
    // The local duplicate guard still applies if the pending list is unavailable.
  }
  confirmWrite('确认提交代客申请留学生吗？', async () => {
    try {
      const result: any = await platformApi.employee.createConvertApply({
        customer_id: customerId,
        approver_id: Number(convertForm.approverId),
        title: convertForm.title || ('代客申请：' + convertForm.project),
      })
      submittedConversionIds.add(customerId)
      approvalRows.value = [result, ...approvalRows.value]
      notifySuccess('申请已提交，等待管理层一次审批')
    } catch {
      notifyInfo('代客申请接口尚未就绪，当前申请已保留')
    }
  })
}

async function saveCustomer() {
  if (!customerForm.name || !customerForm.phone) {
    ElMessage.warning('请填写姓名和手机号')
    return
  }
  confirmWrite('确认将这条客户信息录入 CRM 吗？提交后将进入研判和跟进流程。', async () => {
    try {
      const created: any = await platformApi.createCustomer({
        name: customerForm.name,
        phone: customerForm.phone,
        gender: customerForm.gender,
        age: Number(customerForm.age) || undefined,
        education: customerForm.education,
        source_channel: 'EMPLOYEE_INPUT',
        background_info: customerForm.note,
      })
      const row = created?.id ? created : { id: Date.now(), ...customerForm, score: '待确认', status: '新录入', owner: '本人', last: '今天' }
      customerRows.value = [row, ...customerRows.value]
      customerDialog.value = false
      notifySuccess('客户已录入，研判结果将在详情页展示')
    } catch {
      notifyInfo('客户接口尚未就绪，当前记录已保存在本地测试集')
      customerDialog.value = false
    }
  })
}

function removeCustomer(customer: any) {
  confirmWrite('确认删除客户“' + customer.name + '”的跟进记录吗？删除后无法恢复。', () => notifySuccess('记录已删除'))
}

function submitLeave() {
  if (!leaveForm.start || !leaveForm.end || !leaveForm.reason) {
    ElMessage.warning('请补全请假信息')
    return
  }
  confirmWrite('确认提交请假申请吗？提交后将通知负责员工审批。', () => {
    leaveDialog.value = false
    notifySuccess('请假申请已提交')
  })
}

function submitReport() {
  if (!reportForm.content) {
    ElMessage.warning('请填写日报内容')
    return
  }
  confirmWrite('确认提交日报吗？提交后将进入日报记录。', async () => {
    try {
      await platformApi.employee.submitReport({ report_date: reportForm.date, content: reportForm.content, status: 'submitted' })
      notifySuccess('日报提交成功')
    } catch {
      notifyInfo('日报接口尚未就绪，当前内容已保留')
    }
  })
}

async function batchApprove() {
  try {
    await platformApi.approvals.batchApprove({ instance_ids: [101, 102, 103], comment: '批量通过' })
    notifySuccess('批量审批已完成')
  } catch {
    notifyInfo('批量审批接口尚未就绪')
  }
}

async function approveItem(item: any) {
  try {
    await platformApi.approvals.approve(item.id || 101, { comment: '同意' })
    notifySuccess('已通过')
  } catch {
    notifyInfo('审批接口尚未就绪')
  }
}

async function rejectItem(item: any) {
  try {
    await platformApi.approvals.reject(item.id || 101, { comment: '请补充材料' })
    notifySuccess('已驳回')
  } catch {
    notifyInfo('审批接口尚未就绪')
  }
}

async function saveEmployeeProfile() {
  try {
    await platformApi.users.updateMe({ real_name: '陈顾问', contact_info: '企业微信：粤教陈顾问' })
    notifySuccess('个人信息已保存')
  } catch {
    notifyInfo('个人信息接口尚未就绪')
  }
}

async function submitTicket() {
  if (!ticketForm.title || !ticketForm.detail) {
    ElMessage.warning('请补全反馈信息')
    return
  }
  confirmWrite('确认提交反馈工单吗？', async () => {
    try {
      await platformApi.student.submitTicket({ content: ticketForm.title, detail: ticketForm.detail })
      notifySuccess('工单已提交')
    } catch {
      notifyInfo('反馈接口尚未就绪，当前内容已保留')
    }
  })
}

async function startPsychChat() {
  try {
    const result: any = await platformApi.student.psychChat({ message: '我想聊聊最近的心情', session_id: 'new' })
    if (typeof result?.emotion_score === 'number') psychScore.value = result.emotion_score
    notifySuccess('情绪对话已开始')
  } catch {
    notifyInfo('心理关怀接口尚未就绪')
  }
}

function exportCsv(name: string) {
  const blob = new Blob(['名称,状态,时间\n客户列表,已导出,2026-10-17'], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name + '.csv'
  link.click()
  URL.revokeObjectURL(url)
  notifySuccess('导出任务已生成')
}

function revealPhone() {
  confirmWrite('确认查看完整手机号吗？该敏感操作会写入操作日志。', () => notifySuccess('完整号码：138 2626 8891'))
}
</script>

<template>
  <div class="workspace">
    <SectionTitle :eyebrow="role" :title="pageTitle" desc="数据按业务模块和接口口径展示。">
    </SectionTitle>

    <template v-if="section === 'home' && role === 'STUDENT'">
      <section class="welcome surface"><div><span class="badge">STUDENT · 德国双元制护理</span><h2>李同学，欢迎回来</h2><p>负责顾问：陈顾问 · 语言班第3个月 · 当前状态：在学</p></div><div class="welcome-score"><small>综合状态</small><strong>72</strong><span>平静偏积极</span></div></section>
      <div class="stat-grid"><StatCard label="待办事项" :value="String((reminders.counts && reminders.counts.academic_ddl) || 3)" note="学业与服务提醒" tone="coral" /><StatCard label="本周课程" value="5" note="下节课程：德语写作" tone="purple" /><StatCard label="申请进度" value="签证办理" note="材料递交中" tone="lime" /><StatCard label="服务状态" value="良好" note="最近更新：今天" tone="amber" /></div>
      <div class="two-column">
        <section class="surface panel"><SectionTitle title="近期课程与 DDL" /><div v-for="(item, index) in studentTodos" :key="item.title" class="task-row"><b>0{{ index + 1 }}</b><div><strong>{{ item.title }}</strong><small>{{ item.due }}</small></div><el-tag :type="item.tone === 'coral' ? 'danger' : item.tone === 'amber' ? 'warning' : 'primary'">{{ item.due }}</el-tag></div></section>
        <section class="surface panel"><SectionTitle title="留学申请进度" /><el-steps direction="vertical" :active="4"><el-step title="材料审核" description="学历公证与语言证明已通过" /><el-step title="申请提交" description="目标院校申请已完成" /><el-step title="收到 Offer" description="护理方向 · 条件录取" /><el-step title="签证办理" description="材料递交中" /><el-step title="行前准备" /><el-step title="已入学" /></el-steps></section>
      </div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'admin'">
      <div class="two-column">
        <section class="surface panel"><SectionTitle title="提交请假申请" desc="支持页面提交，也可以直接使用学生助手代办。" /><el-form label-position="top"><div class="form-grid"><el-form-item label="请假类型"><el-select v-model="leaveForm.type" style="width:100%"><el-option v-for="item in ['事假','病假','考试假','其他']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="开始日期"><el-input v-model="leaveForm.start" placeholder="2026-10-18" /></el-form-item><el-form-item label="结束日期"><el-input v-model="leaveForm.end" placeholder="2026-10-20" /></el-form-item><el-form-item label="预计缺课"><el-input placeholder="3节" /></el-form-item></div><el-form-item label="请假事由"><el-input v-model="leaveForm.reason" type="textarea" :rows="4" /></el-form-item><el-button type="primary" size="large" @click="submitLeave">提交请假申请</el-button></el-form></section>
        <section class="surface panel"><SectionTitle title="申请状态" /><el-timeline><el-timeline-item timestamp="08:41" type="primary">申请已提交</el-timeline-item><el-timeline-item timestamp="08:41">通知已送达负责员工</el-timeline-item><el-timeline-item timestamp="进行中" type="warning">等待审批</el-timeline-item><el-timeline-item>结果通知</el-timeline-item></el-timeline></section>
      </div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'psych'">
      <section class="psych-hero surface"><div><span class="badge">AI 对话式评估 · 一期</span><h2>今日心理状态</h2><p>服务性综合状态评分，不构成医疗诊断。</p></div><div class="score-ring"><strong>{{ psychScore }}</strong><span>/ 100</span><small>平静偏积极</small></div></section>
      <div class="two-column"><section class="surface panel"><SectionTitle title="情绪趋势" desc="近7日综合状态变化" /><div class="line-chart"><div class="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span></div><div class="chart-area"><svg viewBox="0 0 600 220" preserveAspectRatio="none"><polyline points="0,88 100,104 200,126 300,150 400,136 500,118 600,70" fill="none" stroke="#5a50b8" stroke-width="8" stroke-linecap="round" /></svg></div></div></section><section class="surface panel"><SectionTitle title="服务边界" /><ul class="boundary"><li>不提供医疗级心理建议或诊断</li><li>不承诺退费、转学等重大决定</li><li>遇到严重问题，引导联系专业心理咨询师</li><li>识别到高风险会即时通知负责员工</li></ul><el-button type="primary" round @click="startPsychChat">开始一次情绪对话</el-button><p v-if="studentProfile.latest_emotion_tag" class="muted">最近标签：{{ studentProfile.latest_emotion_tag }}</p></section></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'feedback'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="提交反馈工单" desc="普通咨询和建议不会计入投诉周报。" /><el-form label-position="top"><el-form-item label="反馈类型"><el-select style="width:100%" model-value="服务咨询"><el-option v-for="item in ['服务咨询','课程安排','费用问题','住宿生活','投诉建议']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="问题标题"><el-input v-model="ticketForm.title" placeholder="请简要描述问题" /></el-form-item><el-form-item label="详细描述"><el-input v-model="ticketForm.detail" type="textarea" :rows="5" /></el-form-item><el-checkbox v-model="ticketForm.formal">确认这是正式投诉（仅正式投诉进入投诉周报）</el-checkbox><el-button type="primary" style="margin-top:18px" @click="submitTicket">提交工单</el-button></el-form></section><section class="surface panel"><SectionTitle title="我的工单" /><div v-for="item in (studentTickets.length ? studentTickets : [{content:'宿舍网络连接不稳定',status:'处理中',create_time:'2026-10-12'},{content:'选课系统操作咨询',status:'已解决',create_time:'2026-09-28'}])" :key="item.id || item.content" class="ticket-row"><div><b>{{ item.content || item.t }}</b><small>{{ item.create_time || '2026-10-12' }}</small></div><el-tag :type="(item.status || item.s) === '已解决' ? 'success' : 'warning'">{{ item.status || item.s }}</el-tag></div></section></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'academic'">
      <div class="stat-grid"><StatCard label="7日内到期" value="3" tone="coral" /><StatCard label="待提交作业" value="2" tone="amber" /><StatCard label="当前 GPA" value="87.2" note="高于专业平均6.4分" tone="lime" /><StatCard label="已设置提醒" value="4" tone="purple" /></div>
      <section class="surface panel"><SectionTitle title="DDL 与考试安排" /><div v-for="item in [{t:'Data Structures 课程作业',d:'10月18日 23:59',tag:'紧急'},{t:'Academic Writing 论文初稿',d:'10月20日 17:00',tag:'5天'},{t:'Advanced Programming 期中考试',d:'10月22日 09:00',tag:'考试'}]" :key="item.t" class="academic-row"><el-tag :type="item.tag === '紧急' ? 'danger' : 'warning'">{{ item.tag }}</el-tag><div><b>{{ item.t }}</b><small>截止时间 {{ item.d }}</small></div><el-button text type="primary">查看详情</el-button></div></section>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'progress'">
      <section class="surface panel"><SectionTitle title="留学申请进度追踪" desc="材料审核 → 申请提交 → 收到 Offer → 签证办理 → 行前准备 → 已入学" /><el-steps :active="3" align-center><el-step title="材料审核" /><el-step title="申请提交" /><el-step title="收到 Offer" /><el-step title="签证办理" /><el-step title="行前准备" /><el-step title="已入学" /></el-steps><div class="progress-note"><b>当前阶段：签证办理</b><p>材料递交中，预计3周出结果。负责员工会持续更新备注和时间。</p></div></section>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'life'">
      <div class="life-grid"><article v-for="item in (lifeFaqRows.length ? lifeFaqRows : ['住宿指南','交通指南','医疗健康','法律与安全','紧急联系','生活常见问题'])" :key="item" class="surface life-card"><h3>{{ item }}</h3><p>查看当地生活知识、注意事项和服务渠道。</p><el-button text type="primary">查看指南</el-button></article></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'more'">
      <SectionTitle title="更多服务" desc="以下服务均为可选项目，不影响你已有的常规服务权益。" />
      <div class="service-grid"><article v-for="item in (moreServiceRows.length ? moreServiceRows : ['学业规划','课程升级','背景提升','语言进阶','职业发展','定制服务'])" :key="item" class="surface service-card"><div class="service-icon">+</div><h3>{{ item }}</h3><p>基于当前阶段和学业表现，为你匹配合适的成长资源。</p><el-button round>了解详情</el-button></article></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'profile'">
      <section class="surface profile-card"><SectionTitle title="账号资料" /><el-form label-position="top"><div class="form-grid"><el-form-item label="姓名"><el-input model-value="李同学" /></el-form-item><el-form-item label="手机号"><el-input model-value="138****2266" /></el-form-item><el-form-item label="所属项目"><el-input model-value="德国双元制 · 护理" /></el-form-item><el-form-item label="负责顾问"><el-input model-value="陈顾问" /></el-form-item></div><el-button type="primary" @click="confirmWrite('确认保存个人信息修改吗？', saveEmployeeProfile)">保存修改</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'home'">
      <section class="welcome surface"><div><span class="badge">EMPLOYEE · 新加坡事业部</span><h2>陈顾问，上午好</h2><p>今日有4项待办，1条重要提醒，当前视图仅显示归属本人的数据。</p></div><el-button type="primary" round @click="customerDialog = true"><el-icon><Plus /></el-icon>录入新客户</el-button></section>
      <div class="stat-grid"><StatCard label="今日待办" value="4" note="2条高优先级" tone="coral" /><StatCard label="名下客户" value="18" note="本月新增 5" tone="purple" /><StatCard label="跟进中 / 已转化" value="10 / 6" note="转化率 33.3%" tone="lime" /><StatCard label="待我审批" value="3" note="1项即将超时" tone="amber" /></div>
      <div class="quick-grid"><button v-for="item in employeeMenu" :key="item.label" @click="item.action"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><el-icon><ArrowRight /></el-icon></button></div>
      <div class="two-column"><section class="surface panel"><SectionTitle title="今日待办" /><div v-for="item in ['跟进赵六 · 德国双元制方案','审批李娜的请假申请','补充王五的费用沟通记录']" :key="item" class="task-row"><b>!</b><div><strong>{{ item }}</strong><small>点击进入对应页面处理</small></div><el-button text type="primary">处理</el-button></div></section><section class="surface panel"><SectionTitle title="客户跟进提醒" /><div class="bars"><div v-for="height in [38,62,48,82,65,91,74]" :key="height" class="bar" :style="{ height: height + '%' }"></div></div></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'customers'">
      <SectionTitle title="我的客户" desc="普通员工只能查看自己名下的客户，管理层可查看全域数据。"><el-button type="primary" :icon="Plus" @click="customerDialog = true">录入客户</el-button></SectionTitle>
      <div class="toolbar surface"><el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索姓名、手机号或项目" clearable /><el-button :icon="Download" @click="exportCsv('客户列表')">导出 CSV</el-button></div>
      <section class="surface table-card"><el-table :data="filteredCustomers" @row-click="(row:any) => activeCustomer = row"><el-table-column prop="name" label="客户" width="130" /><el-table-column prop="phone" label="手机号" width="130" /><el-table-column prop="project" label="意向项目" /><el-table-column prop="score" label="研判结论" width="110"><template #default="{ row }"><el-tag :type="row.score === '符合' ? 'success' : row.score === '待确认' ? 'warning' : 'info'">{{ row.score }}</el-tag></template></el-table-column><el-table-column prop="status" label="状态" width="110" /><el-table-column prop="owner" label="跟进人" width="100" /><el-table-column prop="last" label="最后跟进" width="100" /><el-table-column label="操作" width="180"><template #default="{ row }"><el-button text type="primary" @click.stop="activeCustomer = row">详情</el-button><el-button text type="danger" :icon="Delete" @click.stop="removeCustomer(row)" /></template></el-table-column></el-table></section>
      <el-drawer v-model="activeCustomer" title="客户详情" size="min(620px, 94vw)"><template v-if="activeCustomer"><div class="customer-head"><div><h2>{{ activeCustomer.name }}</h2><p>{{ activeCustomer.project }} · {{ activeCustomer.phone }}</p></div><el-tag type="success">{{ activeCustomer.score }}</el-tag></div><h3>研判结果</h3><div class="assessment"><div><small>新加坡项目</small><b>{{ activeCustomer.score }}</b><p>学历、年龄和目标方向已形成初步匹配，缺失信息已列入跟进建议。</p></div><div><small>中德项目</small><b>待确认</b><p>德语能力、封闭实训接受度和无犯罪记录需要电话核实。</p></div></div><h3>推荐项目</h3><el-tag v-for="item in ['新加坡国际本硕升学计划','中德精英人才共建计划']" :key="item" class="recommend">{{ item }}</el-tag><h3>跟进记录</h3><el-timeline><el-timeline-item>官网注册留资 · 2026-10-13</el-timeline-item><el-timeline-item>Agent 自动采集 · 2026-10-13</el-timeline-item><el-timeline-item>员工首次跟进 · 2026-10-14</el-timeline-item></el-timeline><div class="drawer-actions"><el-button type="primary" @click="confirmWrite('确认添加一条跟进记录吗？', () => notifySuccess('跟进记录已添加'))">添加跟进</el-button><el-button @click="confirmWrite('确认更新客户状态吗？', () => notifySuccess('状态已更新'))">更新状态</el-button></div></template></el-drawer>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'convert'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="代客申请留学生" desc="一次审批：员工申请，管理层审批。" /><el-form label-position="top"><el-form-item label="选择意向客户"><el-select v-model="convertForm.customerId" style="width:100%"><el-option v-for="item in customerRows" :key="item.id" :label="item.name + '（' + item.project + '）'" :value="item.id" /></el-select></el-form-item><el-form-item label="转化项目"><el-select v-model="convertForm.project" style="width:100%"><el-option v-for="item in projects.slice(0,3)" :key="item.id" :label="item.title" :value="item.title" /></el-select></el-form-item><el-form-item label="转化理由 / 备注"><el-input v-model="convertForm.title" type="textarea" :rows="4" /></el-form-item><el-button type="primary" @click="submitConvertApply">提交审批申请</el-button></el-form></section><section class="surface panel"><SectionTitle title="学生流程审批" /><div v-for="item in (approvalRows.length ? approvalRows : [{title:'张三 · 病假申请',status:'pending'},{title:'陈同学 · 成绩复核',status:'pending'},{title:'李同学 · 宿舍调换',status:'approved'}])" :key="item.id || item.title" class="ticket-row"><div><b>{{ item.title || item.t }}</b><small>学生端提交 · {{ item.created_at || '2026-10-15' }}</small></div><el-tag :type="item.status === 'approved' ? 'success' : 'warning'">{{ item.status || item.s }}</el-tag></div></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'reports'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="提交日报" desc="次日0点前可补提；之后需要发起日报补报申请。" /><el-form label-position="top"><el-form-item label="日报日期"><el-input v-model="reportForm.date" /></el-form-item><el-form-item label="口述 / 文字内容"><el-input v-model="reportForm.content" type="textarea" :rows="10" placeholder="今天跟进了哪些客户？明天计划做什么？" /></el-form-item><el-button @click="notifyInfo('AI 整理预览已生成')">AI 整理日报</el-button><el-button type="primary" @click="submitReport">确认提交</el-button></el-form></section><section class="surface panel"><SectionTitle title="近7日日报" /><div v-for="item in ['10-14 跟进3客户 · 2方案','10-13 跟进2客户 · 1方案','10-12 跟进4客户 · 3方案']" :key="item" class="task-row"><b>✓</b><div><strong>{{ item }}</strong><small>已提交</small></div><el-button text>查看</el-button></div></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'scores'">
      <SectionTitle title="成绩录入" desc="录入后学生可在个人信息页查看，并同步触发学业提醒。" />
      <div class="two-column"><section class="surface panel"><el-form label-position="top"><el-form-item label="选择学生"><el-select style="width:100%" model-value="张三"><el-option label="张三 · STU-2026-001" value="张三" /></el-select></el-form-item><el-form-item label="学期"><el-select style="width:100%" model-value="2026秋季"><el-option label="2026秋季" value="2026秋季" /></el-select></el-form-item><el-form-item label="课程名称"><el-input placeholder="Advanced Programming" /></el-form-item><el-form-item label="成绩（0-100）"><el-input placeholder="88" /></el-form-item><el-button type="primary" @click="confirmWrite('确认录入该成绩吗？', () => notifySuccess('成绩已录入'))">提交录入</el-button></el-form></section><section class="surface panel"><SectionTitle title="已录入成绩" /><el-table :data="[{course:'Advanced Programming',score:88},{course:'Data Structures',score:91},{course:'Academic Writing',score:85}]"><el-table-column prop="course" label="课程" /><el-table-column prop="score" label="成绩" width="100" /></el-table></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'org'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="组织架构查询" desc="联系方式默认脱敏，查看完整号码需要二次确认。" /><el-input :prefix-icon="Search" placeholder="搜索姓名或部门" /><el-tree :data="[{label:'广东省教育服务有限公司',children:[{label:'新加坡事业部',children:[{label:'陈顾问'},{label:'李四'}]},{label:'德国事业部',children:[{label:'赵敏'}]}]}]" default-expand-all /></section><section class="surface panel"><SectionTitle title="新人指引" /><div v-for="item in ['办公环境快速导航','IT支持与设备使用','团队协作与沟通','公司文化与价值观','新人成长与资源支持']" :key="item" class="task-row"><b>0{{ item.length % 4 + 1 }}</b><div><strong>{{ item }}</strong><small>知识库 + 引导式流程</small></div><el-button text type="primary">打开</el-button></div><el-button type="primary" round @click="revealPhone">查看脱敏联系方式</el-button></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'todos'">
      <div class="stat-grid"><StatCard label="客户跟进" value="2" tone="amber" /><StatCard label="待审批" value="3" tone="coral" /><StatCard label="反馈处理" value="1" tone="purple" /><StatCard label="系统提醒" value="4" tone="lime" /></div>
      <section class="surface panel"><SectionTitle title="待办与消息" /><div v-for="item in ['跟进赵六 · 德国双元制方案','处理宿舍网络反馈工单','补充王五的费用沟通记录','完成今日日报']" :key="item" class="task-row"><b>!</b><div><strong>{{ item }}</strong><small>今日到期 · 点击进入处理</small></div><el-button text type="primary">处理</el-button></div></section>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'profile'">
      <section class="surface profile-card"><SectionTitle title="账号资料" /><el-form label-position="top"><div class="form-grid"><el-form-item label="姓名"><el-input model-value="陈顾问" /></el-form-item><el-form-item label="手机号"><el-input model-value="138****2266" /></el-form-item><el-form-item label="部门"><el-input model-value="新加坡事业部" /></el-form-item><el-form-item label="企业微信"><el-input model-value="粤教陈顾问" /></el-form-item></div><el-button type="primary" @click="confirmWrite('确认保存个人信息修改吗？', () => notifySuccess('个人信息已保存'))">保存修改</el-button><el-button @click="confirmWrite('确认修改密码吗？', () => notifySuccess('密码修改入口已打开'))">修改密码</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'home'">
      <section class="welcome surface">
        <div>
          <span class="badge">MANAGER · 全域权限</span>
          <h2>经营看板概览</h2>
          <p>覆盖全域客户经营、业绩概览、销售漏斗和管理待办，数据按现有业务模块口径展示。</p>
        </div>
        <el-tag type="success">数据更新于 09:30</el-tag>
      </section>

      <div class="stat-grid">
        <StatCard label="新增意向数" value="183" note="较上月 +12.4%" tone="purple" />
        <StatCard label="转化率" value="21.4%" note="较上月 +1.8pt" tone="lime" />
        <StatCard label="签约金额" value="暂无数据" note="签约金额数据源待接入" tone="amber" />
        <StatCard label="在办学生数" value="689" note="服务满意度 96.8%" tone="coral" />
        <StatCard label="投诉率" value="3.2%" note="本周正式投诉 3 起" tone="purple" />
        <StatCard label="待我审批" value="6" note="含转化、请假和员工流程" tone="coral" />
      </div>

      <div class="manager-dashboard-grid">
        <section class="surface panel funnel-panel">
          <SectionTitle title="全域客户转化漏斗" desc="从访客触达到成功转化的全域数据，可下钻到对应客户名单。" />
          <div class="funnel">
            <div v-for="item in [{n:'访客触达',v:'8,420',p:100},{n:'意向咨询',v:'1,286',p:76},{n:'有效线索',v:'762',p:56},{n:'深度跟进',v:'328',p:38},{n:'成功转化',v:'42',p:20}]" :key="item.n" :style="{ width: item.p + '%' }">
              <b>{{ item.n }}</b><span>{{ item.v }}</span>
            </div>
          </div>
          <div class="funnel-foot"><span>本月数据</span><span>异常环节会触发预警</span></div>
        </section>

        <section class="surface panel">
          <SectionTitle title="各业务线表现" />
          <div v-for="item in [{n:'新加坡国际本硕',v:'31 人 / 35%',p:78},{n:'德国双元制',v:'38 人 / 40%',p:92},{n:'国际留学',v:'24 人 / 30%',p:62},{n:'国际研学',v:'17 人 / 25%',p:46}]" :key="item.n" class="performance-row">
            <div><b>{{ item.n }}</b><span>{{ item.v }}</span></div>
            <el-progress :percentage="item.p" :show-text="false" />
          </div>
        </section>
      </div>

      <div class="two-column">
        <section class="surface panel">
          <SectionTitle title="全域客户数据" desc="按员工、经理和状态筛选，支持查看研判结果和变更归属。">
            <el-button text type="primary" @click="router.push('/app/manager/customers')">进入客户管理</el-button>
          </SectionTitle>
          <el-table :data="customerRows.slice(0, 4)">
            <el-table-column prop="name" label="客户" width="110" />
            <el-table-column prop="project" label="意向项目" />
            <el-table-column prop="score" label="研判" width="95" />
            <el-table-column prop="status" label="状态" width="105" />
            <el-table-column prop="owner" label="跟进人" width="90" />
          </el-table>
        </section>
        <section class="surface panel">
          <SectionTitle title="近期预警与待办" />
          <div v-for="item in ['综合转化部业绩偏低，完成率 45%','5 名客户超过 7 天未跟进','2 例心理预警需重点跟进','投诉周报已生成，3 起均在 24h 内闭环']" :key="item" class="task-row">
            <b>!</b><div><strong>{{ item }}</strong><small>点击进入对应模块处理</small></div>
            <el-button text type="primary">查看</el-button>
          </div>
        </section>
      </div>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'reports'">
      <!-- M5-05.1~05.9：报告列表 → 详情 → 下钻 → 导出 真实接口闭环 -->
      <template v-if="!selectedReport">
        <div class="toolbar surface">
          <el-select v-model="reportFilterType" clearable placeholder="全部报告类型" style="width:220px" @change="reportPage = 1; loadReports()">
            <el-option v-for="t in REPORT_TYPES" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
          <el-button :icon="Refresh" @click="loadReports()">刷新</el-button>
        </div>
        <el-alert v-if="reportError" :title="reportError" type="warning" show-icon :closable="false" />
        <section class="surface table-card">
          <el-skeleton v-if="reportLoading" :rows="5" animated style="padding:16px" />
          <el-empty v-else-if="!reportError && reportList.length === 0" description="暂无报告——在下方选择类型手动生成" />
          <template v-else>
            <el-table :data="reportList" @row-click="openReport">
              <el-table-column label="报告" min-width="220">
                <template #default="{ row }">
                  <b>{{ row.report_title || typeName(row.report_type) }}</b>
                  <el-tag v-if="row.data_source_status === 'mock'" size="small" type="warning" style="margin-left:8px">演示数据</el-tag>
                  <el-tag v-else size="small" type="success" style="margin-left:8px">正式数据</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="周期" width="200">
                <template #default="{ row }">{{ String(row.time_range_start || '').slice(0, 10) }} ~ {{ String(row.time_range_end || '').slice(0, 10) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="version" label="版本" width="80" />
              <el-table-column label="生成时间" width="170">
                <template #default="{ row }">{{ String(row.created_at || '').slice(0, 19).replace('T', ' ') }}</template>
              </el-table-column>
              <el-table-column label="操作" width="90">
                <template #default="{ row }"><el-button text type="primary" @click.stop="openReport(row)">详情</el-button></template>
              </el-table-column>
            </el-table>
            <el-pagination v-model:current-page="reportPage" :page-size="reportPageSize" :total="reportTotal" layout="prev, pager, next, total" @current-change="loadReports" style="margin:14px 0 4px; justify-content:flex-end" />
          </template>
        </section>
        <section class="surface panel" style="margin-top:20px">
          <SectionTitle title="手动生成报告" desc="一期为手动生成，无自动调度；重复生成同类型同周期保留历史版本。" />
          <div class="report-gen-grid">
            <button v-for="t in REPORT_TYPES" :key="t.type" class="report-gen-card" :disabled="reportGenerating !== ''" @click="generateReport(t.type)">
              <b>{{ t.code }}</b><strong>{{ t.name }}</strong><small>{{ t.period }}</small>
              <el-tag v-if="reportGenerating === t.type" size="small" type="info">生成中…</el-tag>
            </button>
          </div>
        </section>
      </template>

      <template v-else>
        <div class="toolbar surface" style="align-items:center">
          <el-button @click="backToReportList">← 返回列表</el-button>
          <b style="font-size:16px">{{ selectedReport.report_title || typeName(selectedReport.report_type) }}</b>
          <el-tag v-if="selectedReport.data_source_status === 'mock'" type="warning">演示数据</el-tag>
          <el-tag v-else type="success">正式数据</el-tag>
          <el-tag :type="selectedReport.status === 'completed' ? 'success' : selectedReport.status === 'failed' ? 'danger' : 'warning'">{{ selectedReport.status }}</el-tag>
          <el-tag type="info">V{{ selectedReport.version }}</el-tag>
          <el-button style="margin-left:auto" :icon="Download" type="primary" @click="downloadReportPdf">导出 PDF</el-button>
          <el-button :disabled="reportGenerating !== ''" @click="generateReport(selectedReport.report_type)">
            {{ reportGenerating === selectedReport.report_type ? '重新生成中…' : '重新生成' }}
          </el-button>
        </div>
        <el-skeleton v-if="detailLoading" :rows="6" animated style="padding:16px" class="surface" />
        <template v-else>
          <section class="surface panel">
            <div class="report-meta">
              <span>周期：{{ String(selectedReport.time_range_start || '').slice(0, 10) }} ~ {{ String(selectedReport.time_range_end || '').slice(0, 10) }}</span>
              <span>AI 分析：{{ aiSourceText(selectedReport.report_content) }}</span>
            </div>
            <p v-if="selectedReport.report_content?.summary" class="report-summary-text">{{ selectedReport.report_content.summary }}</p>
            <p v-if="selectedReport.report_content?.analysis" class="report-summary-text">{{ selectedReport.report_content.analysis }}</p>
            <ul v-if="selectedReport.report_content?.suggestions?.length" class="report-suggestions">
              <li v-for="(s, i) in selectedReport.report_content.suggestions" :key="i">{{ s.content }}<small v-if="s.department || s.owner">（{{ s.department || '待指定部门' }} · {{ s.owner || '待指定负责人' }}）</small></li>
            </ul>
          </section>

          <section class="surface table-card" style="margin-top:20px">
            <SectionTitle title="核心指标" />
            <el-table :data="metricRows(selectedReport.report_content?.metrics)" size="small">
              <el-table-column prop="key" label="指标" min-width="220" />
              <el-table-column prop="value" label="数值" width="160" />
            </el-table>
            <p class="muted" style="padding:12px 4px 4px; line-height:1.8">{{ selectedReport.report_content?.data_notes }}</p>
          </section>

          <section class="surface panel" style="margin-top:20px">
            <SectionTitle title="明细下钻" desc="下钻与所选报告同源：正式数据读真实业务表，演示数据读模拟数据；个体信息按角色权限过滤。" />
            <div style="display:flex; gap:10px; margin-bottom:14px">
              <el-button v-if="selectedReport.report_type === 'customer_analysis'" :loading="drillLoading === 'customers'" @click="loadDrill('customers')">客户明细</el-button>
              <el-button v-if="selectedReport.report_type === 'psych_weekly'" :loading="drillLoading === 'psychCases'" @click="loadDrill('psychCases')">心理个案</el-button>
              <el-button v-if="selectedReport.report_type === 'complaint_weekly'" :loading="drillLoading === 'specialCases'" @click="loadDrill('specialCases')">投诉特别案例</el-button>
            </div>
            <el-table v-if="drill.customers.length" :data="drill.customers" size="small">
              <el-table-column prop="name" label="客户" width="120" />
              <el-table-column prop="phone" label="手机号（脱敏）" width="140" />
              <el-table-column prop="status" label="期末状态" width="110" />
              <el-table-column prop="source_channel" label="来源" width="150" />
              <el-table-column prop="sg_conclusion" label="新加坡画像" width="110" />
              <el-table-column prop="de_conclusion" label="德国画像" width="110" />
            </el-table>
            <el-table v-if="drill.psychCases.length" :data="drill.psychCases" size="small">
              <el-table-column prop="student_id" label="学生ID" width="100" />
              <el-table-column prop="risk_level" label="风险等级" width="100" />
              <el-table-column prop="emotion_tag" label="情绪标签" width="120" />
              <el-table-column prop="responsible_employee_id" label="负责员工ID" width="120" />
            </el-table>
            <el-table v-if="drill.specialCases.length" :data="drill.specialCases" size="small">
              <el-table-column prop="ticket_id" label="工单号" width="120" />
              <el-table-column prop="owner_id" label="负责人ID" width="120" />
              <el-table-column prop="progress" label="处理进度" />
            </el-table>
            <el-empty v-if="selectedReport.report_type === 'customer_analysis' && drill.customers.length === 0 && drillLoading !== 'customers'"
                      description="点击「客户明细」加载下钻数据" :image-size="60" />
          </section>
        </template>
      </template>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'customers'">
      <SectionTitle title="客户管理" desc="查看全域客户、研判结果和跟进记录，支持录入、筛选、下钻和客户再分配。">
        <div class="title-actions">
          <el-button :icon="Plus" @click="customerDialog = true">录入客户</el-button>
          <el-button :icon="Download" @click="exportCsv('全域客户')">导出 CSV</el-button>
        </div>
      </SectionTitle>
      <div class="toolbar surface">
        <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索姓名、手机号或项目" clearable />
        <el-select model-value="全部员工" style="width:150px"><el-option label="全部员工" value="all" /><el-option label="李四" value="李四" /><el-option label="赵敏" value="赵敏" /></el-select>
        <el-select model-value="全部状态" style="width:140px"><el-option label="全部状态" value="all" /><el-option label="跟进中" value="跟进中" /><el-option label="已签约" value="已签约" /></el-select>
        <el-button @click="confirmWrite('确认对所选客户执行批量再分配吗？', () => notifySuccess('客户再分配任务已提交'))">批量再分配</el-button>
      </div>
      <section class="surface table-card">
        <el-table :data="filteredCustomers" @row-click="(row:any) => activeCustomer = row">
          <el-table-column type="selection" width="48" />
          <el-table-column prop="name" label="客户" width="120" />
          <el-table-column prop="phone" label="手机号" width="125" />
          <el-table-column prop="project" label="意向项目" />
          <el-table-column prop="score" label="研判结果" width="110" />
          <el-table-column prop="status" label="客户状态" width="110" />
          <el-table-column prop="owner" label="跟进人" width="95" />
          <el-table-column prop="last" label="最后跟进" width="100" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button text type="primary" @click.stop="activeCustomer = row">详情</el-button>
              <el-button text @click.stop="confirmWrite('确认变更客户归属吗？', () => notifySuccess('客户归属已变更'))">改归属</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
      <el-drawer v-model="activeCustomer" title="全域客户详情" size="min(620px, 94vw)">
        <template v-if="activeCustomer">
          <div class="customer-head"><div><h2>{{ activeCustomer.name }}</h2><p>{{ activeCustomer.project }} · {{ activeCustomer.phone }}</p></div><el-tag type="success">{{ activeCustomer.score }}</el-tag></div>
          <h3>全域客户研判</h3>
          <div class="assessment"><div><small>新加坡项目</small><b>{{ activeCustomer.score }}</b><p>画像匹配结果、缺失信息和跟进建议。</p></div><div><small>中德项目</small><b>待确认</b><p>需要核实德语能力、实训接受度和无犯罪记录。</p></div></div>
          <h3>跟进与归属</h3>
          <p class="muted">当前跟进人：{{ activeCustomer.owner }} · 支持管理层变更归属</p>
          <div class="drawer-actions"><el-button type="primary" @click="confirmWrite('确认添加跟进记录吗？', () => notifySuccess('跟进记录已添加'))">添加跟进</el-button><el-button @click="confirmWrite('确认变更归属吗？', () => notifySuccess('归属已变更'))">变更归属</el-button></div>
        </template>
      </el-drawer>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'approvals'">
      <SectionTitle title="审批任务" desc="统一处理员工转化申请、请假、日报补报和投诉处理，支持批量通过。">
        <el-button type="primary" @click="confirmWrite('确认批量通过所选申请吗？', batchApprove)">批量通过</el-button>
      </SectionTitle>
      <div class="approval-filters"><el-radio-group model-value="全部"><el-radio-button value="全部">全部</el-radio-button><el-radio-button value="转化申请">转化申请</el-radio-button><el-radio-button value="请假">请假</el-radio-button><el-radio-button value="员工流程">员工流程</el-radio-button></el-radio-group></div>
      <div class="approval-grid">
        <article v-for="item in [{id:101,type:'转化申请',title:'陈顾问申请将王女士转化为留学生',status:'待审批'},{id:102,type:'请假申请',title:'张三提交病假申请',status:'待审批'},{id:103,type:'日报补报',title:'赵敏提交日报补报申请',status:'待审批'}]" :key="item.title" class="surface approval-card">
          <div class="approval-top"><el-checkbox /><el-tag>{{ item.type }}</el-tag><el-tag type="warning">{{ item.status }}</el-tag></div>
          <h3>{{ item.title }}</h3>
          <p>提交时间：2026-10-15 · 一次审批</p>
          <div><el-button type="primary" @click="confirmWrite('确认通过该申请吗？', () => approveItem(item))">通过</el-button><el-button @click="confirmWrite('确认驳回该申请吗？申请人可修改后重新提交。', () => rejectItem(item))">驳回</el-button><el-button text>查看详情</el-button></div>
        </article>
      </div>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'employees'">
      <SectionTitle title="员工账号与权限" desc="一期不设置独立人事角色，员工账号和状态在此统一管理。"><el-button type="primary" :icon="Plus">创建员工账号</el-button></SectionTitle>
      <section class="surface table-card"><el-table :data="[{name:'李四',department:'新加坡事业部',role:'普通员工',customers:18,status:'正常'},{name:'赵敏',department:'德国事业部',role:'普通员工',customers:15,status:'正常'},{name:'周琳',department:'素质教育部',role:'普通员工',customers:12,status:'待开通'}]"><el-table-column prop="name" label="员工" /><el-table-column prop="department" label="部门" /><el-table-column prop="role" label="角色" /><el-table-column prop="customers" label="本月客户" width="110" /><el-table-column prop="status" label="状态" /><el-table-column label="操作"><template #default><el-button text type="primary">权限</el-button></template></el-table-column></el-table></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'permissions'">
      <section class="surface panel permission-panel"><SectionTitle title="权限项配置" desc="一期使用 user_type 粗判和数据隔离，权限项配置界面为管理层工具。" /><el-form label-position="top"><el-form-item label="选择用户"><el-select style="width:100%" model-value="王总"><el-option label="王总 · 总裁" value="王总" /><el-option label="李四 · 普通员工" value="李四" /></el-select></el-form-item><el-checkbox-group :model-value="['manager.view_all_crm','manager.view_reports']"><el-checkbox value="manager.approve_convert">审批转化申请</el-checkbox><el-checkbox value="manager.view_all_crm">查看全部客户</el-checkbox><el-checkbox value="manager.business_dashboard">经营看板</el-checkbox><el-checkbox value="manager.view_reports">查看智能报告</el-checkbox><el-checkbox value="manager.permission_config">权限配置</el-checkbox></el-checkbox-group><el-button type="primary" style="margin-top:22px" @click="confirmWrite('确认保存权限配置吗？', () => notifySuccess('权限配置已保存'))">保存权限配置</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'logs'">
      <SectionTitle title="消息中心与操作日志" desc="展示审批结果、预警通知、系统公告和关键操作记录。" />
      <div class="two-column"><section class="surface panel"><SectionTitle title="消息中心" /><div v-for="item in ['审批结果：李娜请假申请已通过','预警通知：2名学生需重点跟进','系统公告：10月经营分析报告已生成']" :key="item" class="task-row"><b>!</b><div><strong>{{ item }}</strong><small>10分钟前 · 站内消息</small></div></div></section><section class="surface panel"><SectionTitle title="关键操作日志" /><el-table :data="[{time:'09:20',action:'客户状态变更',operator:'李四'},{time:'08:41',action:'电话查看',operator:'陈顾问'},{time:'昨天',action:'客户再分配',operator:'王总'}]"><el-table-column prop="time" label="时间" width="90" /><el-table-column prop="action" label="操作" /><el-table-column prop="operator" label="操作人" /></el-table></section></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'courses'">
      <SectionTitle title="课程与项目" desc="登录后可提交报名咨询。" /><div class="service-grid"><article v-for="item in projects.slice(0,4)" :key="item.id" class="surface service-card"><div class="service-icon">{{ item.category.slice(0,2) }}</div><h3>{{ item.title }}</h3><p>{{ item.summary }}</p><el-button type="primary" round @click="router.push('/projects/' + item.id)">了解并咨询</el-button></article></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'events'">
      <SectionTitle title="活动报名" desc="已登录，可直接报名近期活动。" /><div class="event-list"><div v-for="item in events.slice(0,3)" :key="item.id" class="surface ticket-row"><div><b>{{ item.title }}</b><small>{{ item.date }} · {{ item.format }}</small></div><el-button type="primary" round @click="notifySuccess('报名成功')">报名</el-button></div></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'consult'">
      <SectionTitle title="我的咨询" desc="记录与顾问沟通和报名进度。" /><section class="surface panel"><el-empty description="暂无进行中的咨询"><el-button type="primary" @click="router.push('/projects')">去看看项目</el-button></el-empty></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'org'">
      <SectionTitle title="组织架构查询" desc="查看部门职能、团队层级和同事联系方式；联系方式默认脱敏。" />
      <div class="two-column">
        <section class="surface panel"><el-input :prefix-icon="Search" placeholder="搜索部门或姓名" /><el-tree :data="[{label:'广东省教育服务有限公司',children:[{label:'新加坡事业部',children:[{label:'李四'},{label:'陈顾问'}]},{label:'德国事业部',children:[{label:'赵敏'}]}]}]" default-expand-all /></section>
        <section class="surface panel"><SectionTitle title="组织能力" /><div class="life-grid"><article v-for="item in ['部门职能查询','同事联系方式','团队成员筛选','组织变更记录']" :key="item" class="surface life-card"><h3>{{ item }}</h3><p>按部门、经理和员工维度查看组织数据。</p></article></div></section>
      </div>
    </template>

    <template v-else>
      <section class="surface profile-card"><SectionTitle title="模块详情" /><p class="muted">该页面已按当前角色和模块建立完整结构。后续接入对应接口时，将替换数据来源和操作处理。</p><el-button type="primary" @click="router.push('/app/' + role.toLowerCase() + '/home')">返回工作台</el-button></section>
    </template>
  </div>
    <el-dialog v-model="customerDialog" title="录入意向客户" width="min(620px, 94vw)">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="姓名"><el-input v-model="customerForm.name" /></el-form-item>
          <el-form-item label="手机号"><el-input v-model="customerForm.phone" /></el-form-item>
          <el-form-item label="性别"><el-select v-model="customerForm.gender" style="width:100%"><el-option label="男" value="男" /><el-option label="女" value="女" /></el-select></el-form-item>
          <el-form-item label="年龄"><el-input v-model="customerForm.age" /></el-form-item>
          <el-form-item label="学历"><el-input v-model="customerForm.education" /></el-form-item>
          <el-form-item label="意向项目"><el-select v-model="customerForm.project" style="width:100%"><el-option label="新加坡本硕" value="新加坡本硕" /><el-option label="德国双元制" value="德国双元制" /><el-option label="国际留学" value="国际留学" /></el-select></el-form-item>
        </div>
        <el-form-item label="补充说明"><el-input v-model="customerForm.note" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="customerDialog = false">取消</el-button><el-button type="primary" @click="saveCustomer">确认录入</el-button></template>
    </el-dialog>
</template>

<style scoped>
.workspace { max-width: 1280px; margin: 0 auto; }
.welcome { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 32px; margin-bottom: 22px; background: var(--ink); color: #fff; }
.welcome h2 { margin: 14px 0 8px; font-size: 31px; }.welcome p { margin: 0; color: #d5d4ee; }
.welcome-score { min-width: 145px; padding: 18px; border: 1px solid #5c579e; border-radius: 17px; text-align: center; }.welcome-score small, .welcome-score span { display: block; color: #c5c3e4; }.welcome-score strong { display: block; margin: 5px 0; color: #8dd933; font-size: 45px; }
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 22px; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 22px; }
.panel { padding: 26px; }
.task-row, .ticket-row, .report-row, .academic-row { display: flex; align-items: center; gap: 14px; padding: 15px 0; border-bottom: 1px solid var(--line); }
.task-row:last-child, .ticket-row:last-child, .report-row:last-child, .academic-row:last-child { border-bottom: 0; }
.task-row > b, .report-row > b { display: grid; place-items: center; width: 35px; height: 35px; border-radius: 10px; color: var(--ink); background: var(--mint); }
.task-row strong, .task-row small, .ticket-row b, .ticket-row small, .report-row strong, .report-row small, .academic-row b, .academic-row small { display: block; }.task-row > div, .ticket-row > div, .report-row > div, .academic-row > div { flex: 1; }.task-row small, .ticket-row small, .report-row small, .academic-row small { margin-top: 4px; color: var(--muted); }
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 22px 0; }.quick-grid button { display: flex; align-items: center; gap: 12px; padding: 20px; border: 1px solid var(--line); border-radius: 16px; color: var(--ink-deep); background: #fff; cursor: pointer; text-align: left; }.quick-grid button span { flex: 1; font-weight: 800; }
.bars { height: 180px; display: flex; align-items: flex-end; gap: 15px; padding: 20px 10px 0; border-bottom: 2px solid var(--line); }.bar { flex: 1; min-width: 18px; border-radius: 8px 8px 0 0; background: var(--violet); }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 18px; }
.toolbar { display: flex; gap: 12px; padding: 16px; margin-bottom: 18px; }.toolbar .el-input { max-width: 380px; }
.table-card { padding: 8px 18px 18px; overflow: auto; }.drawer-actions { display: flex; gap: 10px; margin-top: 22px; }.customer-head { display: flex; justify-content: space-between; align-items: center; }.customer-head h2 { margin: 0; color: var(--ink-deep); }.customer-head p { color: var(--muted); }.assessment { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.assessment > div { padding: 16px; background: var(--canvas); border-radius: 13px; }.assessment small { color: var(--muted); }.assessment b { display: block; margin: 8px 0; color: var(--violet); font-size: 22px; }.assessment p { margin: 0; color: var(--muted); line-height: 1.7; font-size: 12px; }.recommend { margin: 0 8px 8px 0; }
.psych-hero { display: flex; justify-content: space-between; align-items: center; padding: 34px; color: #fff; background: var(--ink); }.psych-hero h2 { margin: 18px 0 8px; font-size: 36px; }.psych-hero p { color: #d6d5ee; }.score-ring { display: grid; place-items: center; align-content: center; width: 180px; height: 180px; border: 15px solid #80b717; border-right-color: #5b5798; border-radius: 50%; }.score-ring strong { font-size: 55px; line-height: 1; }.score-ring span, .score-ring small { color: #d3d2ec; }
.line-chart { height: 220px; display: flex; gap: 12px; }.chart-y { display: flex; flex-direction: column; justify-content: space-between; color: var(--muted); font-size: 11px; }.chart-area { flex: 1; background: repeating-linear-gradient(to bottom, transparent 0, transparent 48px, var(--line) 49px); }.chart-area svg { width: 100%; height: 100%; }.boundary { padding-left: 20px; color: var(--muted); line-height: 2; }.boundary li::marker { color: var(--lime); }
.life-grid, .service-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 17px; }.life-card, .service-card { padding: 25px; }.life-card h3, .service-card h3 { color: var(--ink-deep); }.life-card p, .service-card p { color: var(--muted); line-height: 1.8; }.service-icon { display: grid; place-items: center; width: 45px; height: 45px; border-radius: 13px; color: var(--ink); background: var(--mint); font-weight: 900; }
.profile-card { padding: 30px; }.event-list { display: grid; gap: 12px; }.ticket-row .el-button { margin-left: auto; }
.report-tabs { display: flex; gap: 10px; margin-bottom: 18px; overflow-x: auto; }.report-tabs button { min-width: 150px; padding: 15px; border: 1px solid var(--line); border-radius: 13px; background: #fff; cursor: pointer; text-align: left; }.report-tabs button.active { color: #fff; border-color: var(--ink); background: var(--ink); }.report-tabs b, .report-tabs span { display: block; }.report-tabs span { margin-top: 7px; font-size: 12px; }
.report-board { padding: 26px; }.report-summary { display: flex; align-items: end; gap: 22px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }.report-summary small, .report-summary strong { display: block; }.report-summary small { color: var(--muted); }.report-summary strong { margin-top: 7px; color: var(--ink-deep); }.report-summary .el-button { margin-left: auto; }.chart-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 20px; margin-top: 22px; }.chart-card { padding: 22px; background: var(--canvas); border-radius: 17px; }.chart-card h3 { margin-top: 0; color: var(--ink-deep); }.bar-chart { height: 235px; display: flex; align-items: flex-end; gap: 17px; padding: 18px 10px 0; border-bottom: 2px solid var(--line); }.bar-chart > div { height: 100%; flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 8px; }.bar-chart i { display: block; width: 35px; min-height: 18px; border-radius: 8px 8px 0 0; background: var(--violet); }.bar-chart span { color: var(--muted); font-size: 11px; }.chart-card ul { padding-left: 19px; color: var(--muted); line-height: 2; }
.approval-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 17px; }.approval-card { padding: 24px; }.approval-card h3 { min-height: 50px; color: var(--ink-deep); }.approval-card p { color: var(--muted); }.approval-card > div { display: flex; gap: 8px; margin-top: 20px; }
.permission-panel { max-width: 760px; padding: 32px; }.permission-panel .el-checkbox { display: flex; margin: 13px 0; }
@media (max-width: 1050px) { .stat-grid { grid-template-columns: repeat(2, 1fr); }.quick-grid { grid-template-columns: repeat(2, 1fr); }.approval-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .two-column, .chart-grid, .life-grid, .service-grid { grid-template-columns: 1fr; }.form-grid, .assessment { grid-template-columns: 1fr; }.welcome, .psych-hero, .report-summary { align-items: flex-start; flex-direction: column; }.toolbar { flex-direction: column; }.toolbar .el-input { max-width: none; }.report-tabs button { min-width: 135px; } }
.report-desc { margin: -8px 0 18px; line-height: 1.7; }
.title-actions { display: flex; gap: 8px; }
.approval-filters { margin-bottom: 18px; }
.approval-top { display: flex; align-items: center; gap: 8px; }
.report-gen-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }
.report-gen-card { display: flex; flex-direction: column; align-items: flex-start; gap: 7px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; cursor: pointer; text-align: left; }
.report-gen-card:disabled { opacity: .55; cursor: not-allowed; }
.report-gen-card b { color: var(--violet); font-size: 18px; }
.report-gen-card strong { color: var(--ink-deep); font-size: 14px; }
.report-gen-card small { color: var(--muted); }
.report-meta { display: flex; gap: 22px; color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.report-summary-text { margin: 8px 0; line-height: 1.9; }
.report-suggestions { padding-left: 20px; line-height: 2; }
.report-suggestions small { color: var(--muted); }
@media (max-width: 1050px) { .report-gen-grid { grid-template-columns: repeat(2, 1fr); } }
</style>


<style scoped>
.manager-dashboard-grid { display: grid; grid-template-columns: 1.2fr .8fr; gap: 20px; margin-top: 22px; }
.funnel { display: grid; gap: 10px; margin: 24px 0; }
.funnel > div { min-width: 42%; height: 54px; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; color: #fff; background: #5a50b8; border-radius: 12px; box-shadow: 0 8px 18px rgba(45,43,115,.12); }
.funnel > div:nth-child(2) { background: #6c64c2; }
.funnel > div:nth-child(3) { background: #7b73ca; }
.funnel > div:nth-child(4) { background: #8b83d1; }
.funnel > div:nth-child(5) { background: #80b717; color: #25235e; }
.funnel b { font-size: 15px; }
.funnel span { font-size: 18px; font-weight: 800; }
.funnel-foot { display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; }
.performance-row { display: grid; grid-template-columns: 180px 1fr; align-items: center; gap: 14px; padding: 13px 0; border-bottom: 1px solid var(--line); }
.performance-row:last-child { border-bottom: 0; }
.performance-row b, .performance-row span { display: block; }
.performance-row b { color: var(--ink-deep); }
.performance-row span { margin-top: 4px; color: var(--muted); font-size: 12px; }
@media (max-width: 760px) {
  .manager-dashboard-grid { grid-template-columns: 1fr; }
  .performance-row { grid-template-columns: 1fr; }
}
</style>
