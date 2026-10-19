<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRight,
  Delete,
  Document,
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
import { REPORT_TYPES, typeName } from '../config/reports'
import { platformApi, fallbackState } from '../api/platform'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const role = computed(() => String(route.params.role || 'PROSPECT').toUpperCase())
const section = computed(() => String(route.params.section || 'home'))
const keyword = ref('')
const customerDialog = ref(false)
const leaveDialog = ref(false)
const psychScore = ref<number | string>('—')
const customerForm = reactive({ name: '', phone: '', gender: '', age: '', education: '', project: '新加坡本硕', note: '' })
const leaveForm = reactive({ type: '事假', start: '', end: '', reason: '' })
const ticketForm = reactive({ type: '服务咨询', title: '', detail: '', formal: false })
const reportForm = reactive({ date: new Date().toISOString().slice(0, 10), content: '' })
const convertForm = reactive({ customerId: 1, project: '新加坡国际本硕升学计划', title: '', approverId: 4 })
const submittedConversionIds = new Set<number>()
const activeCustomer = ref<any>(null)
const customerRows = ref<any[]>([])
// 访客页与转化申请表单用的公开列表（走 platformApi，含懒加载演示数据兜底）
const publicProjects = ref<any[]>([])
const publicEvents = ref<any[]>([])
const selectedCustomerIds = ref<number[]>([])
const reassignFromId = ref<number | undefined>()
const reassignToId = ref<number | undefined>()
const reassignDialogTargetId = ref<number | undefined>()
const reassignDialog = ref(false)
const reassignCustomer = ref<any>(null)
const customerOwnerFilter = ref('all')
const customerStatusFilter = ref('all')
const notificationRows = ref<any[]>([])
const reminders = ref<any>({})
const approvalRows = ref<any[]>([])
const studentProfile = ref<any>({})
const studentTickets = ref<any[]>([])
const lifeFaqRows = ref<any[]>([])
const moreServiceRows = ref<any[]>([])
const studentReminders = ref<any>({})
const studentAcademic = ref<any>({})
const studentProgressRows = ref<any[]>([])
const studentLeaveRows = ref<any[]>([])
const permissionUserId = ref<number | undefined>()
// 权限勾选的编辑态：切换用户时同步为该用户的真实权限，保存时整体覆盖写入
const permissionDraft = ref<string[]>([])
// 创建员工账号弹窗：后端 POST /employee/users 必填 username / password / real_name / user_type
const createUserDialog = ref(false)
const createUserForm = reactive({ real_name: '', username: '', phone: '', password: '', user_type: 'EMPLOYEE', department: '', employee_role: '' })
const scoreForm = reactive({ studentId: 2, semester: String(), courseName: String(), score: 0 })
const scoreRows = ref([] as any[])
const dailyReportRows = ref([] as any[])
const activeReport = ref(null as any)
const reportDialog = ref(false)

// 管理层经营看板 / 审批中心，员工待办与客户统计，组织树（均绑定后端真实接口）
const dashboardData = ref<any>({})
const approvalsData = ref<any>({})
const todoRows = ref<any[]>([])
const operationLogRows = ref<any[]>([])
const profileStats = ref<any>({})
const orgTree = ref<any[]>([])
const orgTreeProps = { label: 'name', children: 'children' }
const orgKeyword = ref('')
const orgMembers = ref<any[]>([])
const revealedPhones = ref<Record<number, string>>({})
const employeeRows = ref<any[]>([])
const selectedApprovals = ref<number[]>([])
const approvalFilter = ref('全部')
const updatedAtLabel = ref('—')
// 客户来源渠道中文映射（后端 source_channel 枚举）
const sourceLabel: Record<string, string> = { WEBSITE_REGISTER: '官网注册', CS_LEAD: '客服线索', EMPLOYEE_INPUT: '员工录入' }
const todoStatusLabel: Record<string, string> = { pending: '待处理', in_progress: '处理中', done: '已完成' }
const todoPriorityLabel: Record<string, string> = { low: '低', medium: '中', high: '高' }
const logModuleLabel: Record<string, string> = { auth: '认证', crm: '客户', cs: '客服', employee: '员工', report: '日报', student: '学生', M3: '系统' }
const logActionLabel: Record<string, string> = { create: '新增', update: '修改', delete: '删除', login: '登录', export: '导出', phone_reveal: '查看完整手机号' }
const approvalBizLabel: Record<string, string> = { leave: '请假申请', convert: '转化申请', late_report: '日报补报', complaint: '投诉处理' }
const approvalStatusLabel: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已驳回' }
// 客户状态 6 态：DB 存英文编码（后端 customer_service.CUSTOMER_STATUSES），历史/演示数据为中文，筛选项以真实编码为 value
const customerStatusOptions = [
  { label: '新录入', value: 'NEW' },
  { label: '跟进中', value: 'FOLLOWING' },
  { label: '意向强烈', value: 'STRONG' },
  { label: '已签约', value: 'SIGNED' },
  { label: '已入学', value: 'ENROLLED' },
  { label: '已流失', value: 'LOST' },
]
function customerStatusKey(status: string) {
  const hit = customerStatusOptions.find((option) => option.label === status)
  return hit ? hit.value : status
}

const mgrOverview = computed(() => dashboardData.value?.overview || {})
const mgrCustomers = computed(() => dashboardData.value?.customers || {})
const mgrPendingTotal = computed(() => approvalsData.value?.stats?.pending_total ?? '—')
// 审批筛选：按 radio 标签语义映射 biz_type（转化申请=convert、请假=leave、员工流程=日报补报/投诉）
const approvalFilterBizTypes: Record<string, string[]> = { '转化申请': ['convert'], '请假': ['leave'], '员工流程': ['late_report', 'complaint'] }
const filteredApprovalItems = computed<any[]>(() => {
  const types = approvalFilterBizTypes[approvalFilter.value]
  return types ? approvalRows.value.filter((item: any) => types.includes(item.biz_type)) : approvalRows.value
})
// 漏斗：以最大环节为 100% 计算条形宽度，与后端 dashboard.customers.funnel 口径一致
const funnelRows = computed(() => {
  const list: any[] = mgrCustomers.value.funnel || []
  const max = Math.max(...list.map((x) => x.count || 0), 1)
  return list.map((x) => ({ n: x.stage, v: String(x.count ?? 0), p: Math.round(((x.count || 0) / max) * 100) }))
})
// 客户来源渠道分布：以最大来源为 100% 计算条形宽度，与后端 dashboard.customers.by_source 口径一致
const sourceRows = computed(() => {
  const list: any[] = mgrCustomers.value.by_source || []
  const max = Math.max(...list.map((x) => x.count || 0), 1)
  return list.map((x) => ({
    n: sourceLabel[x.source] || x.source || '未知来源',
    v: String(x.count ?? 0) + ' 人',
    p: Math.round(((x.count || 0) / max) * 100),
  }))
})

// 学生首页「近期课程与 DDL」：来自提醒聚合 academic_ddl（真实字段 title/course_name/due_time/days_left）
const studentDdlRows = computed(() => itemsOf(studentReminders.value?.academic_ddl).map((item: any) => ({
  title: item.title,
  due: String(item.due_time || '').slice(0, 10) || '—',
  tone: (item.days_left ?? 99) <= 1 ? 'coral' : (item.days_left ?? 99) <= 2 ? 'amber' : 'blue',
})))
// 学生学业页：DDL 列表取 academic_items；统计卡由 academic_items/score_summary 真实字段推导
const studentAcademicItems = computed(() => itemsOf(studentAcademic.value?.academic_items))
const studentAcademicStats = computed(() => {
  const now = Date.now()
  const week = 7 * 24 * 60 * 60 * 1000
  const items = studentAcademicItems.value
  const dueWithin7d = items.filter((i: any) => {
    const t = new Date(i.due_time).getTime()
    return !isNaN(t) && t >= now && t - now <= week
  }).length
  const pending = items.filter((i: any) => i.item_type === '作业' && new Date(i.due_time).getTime() >= now).length
  const pushed = items.filter((i: any) => i.reminder_sent).length
  const summary = studentAcademic.value?.score_summary || {}
  return {
    due7d: dueWithin7d,
    pending,
    gpa: summary.average != null ? String(summary.average) : '—',
    pushed,
    scoreCount: summary.count ?? 0,
  }
})

// 学生申请进度：GET /student/progress（真实阶段/状态/备注），按更新时间升序作为步骤顺序
const studentProgressSteps = computed(() => [...studentProgressRows.value].sort(
  (a: any, b: any) => new Date(a.update_time || 0).getTime() - new Date(b.update_time || 0).getTime(),
))
const studentProgressCurrent = computed(() => studentProgressSteps.value[studentProgressSteps.value.length - 1] || null)
// 进度状态中文化：后端 status 是英文枚举（waiting/in_progress/completed…），不直接展示原文
const progressStatusLabel: Record<string, string> = { waiting: '待处理', pending: '待处理', in_progress: '进行中', doing: '进行中', completed: '已完成', done: '已完成' }
function progressStatusText(item: any) {
  if (!item) return ''
  return item.notes || progressStatusLabel[item.status] || item.status || ''
}
// 学生首页「待办事项」：提醒聚合 counts（学业 DDL + 服务结果 + 进度更新）真实合计
const studentReminderTotal = computed(() => {
  const c = studentReminders.value?.counts || {}
  return (c.academic_ddl ?? 0) + (c.leave_results ?? 0) + (c.ticket_updates ?? 0) + (c.progress_updates ?? 0)
})
// 情绪趋势：近 7 天评估记录（emotion_history: {time, tag, score}）映射为折线坐标；不足 2 点不画线
const emotionTrendPoints = computed(() => {
  const history = Array.isArray(studentProfile.value?.emotion_history) ? studentProfile.value.emotion_history : []
  const since = Date.now() - 7 * 24 * 60 * 60 * 1000
  const points = history
    .map((h: any) => ({ t: new Date(h?.time).getTime(), score: Number(h?.score) }))
    .filter((h: any) => !isNaN(h.t) && h.t >= since && Number.isFinite(h.score))
    .sort((a: any, b: any) => a.t - b.t)
  if (points.length < 2) return ''
  return points
    .map((p: any, i: number) => `${Math.round((i / (points.length - 1)) * 600)},${Math.round(220 - (Math.max(0, Math.min(100, p.score)) / 100) * 220)}`)
    .join(' ')
})
// 权限配置：选中员工的真实权限列表（GET /employee/users 的 permissions 字段）
const permissionUser = computed(() => employeeRows.value.find((item: any) => item.id === permissionUserId.value) || null)
const permissionChecked = computed<string[]>(() => (Array.isArray(permissionUser.value?.permissions) ? permissionUser.value.permissions : []))
// 权限项字典：key 必须与后端 sys_user.permissions 的真实取值一致
// （目录见 backend/scripts/seed_supplement_v6_11_13.py 的 PERMS：ADMIN/MANAGER/EMPLOYEE 三组并集）
const permissionOptions = [
  { key: 'report:view', label: '查看智能报告' },
  { key: 'report:export', label: '导出报表' },
  { key: 'approval:manage', label: '审批管理' },
  { key: 'employee:manage', label: '员工管理' },
  { key: 'customer:view', label: '查看客户' },
  { key: 'customer:edit', label: '编辑客户' },
  { key: 'report:daily', label: '提交日报' },
  { key: 'todo:view', label: '查看待办' },
  { key: 'system:manage', label: '系统管理' },
  { key: 'user:manage', label: '用户管理' },
]

watch(permissionUserId, () => { permissionDraft.value = [...permissionChecked.value] })

// 保存权限配置：PUT /employee/users/{id}/permissions（覆盖式写入），成功后同步本地行的真实权限
async function savePermissionConfig() {
  const user = permissionUser.value
  if (!user) { notifyInfo('请先选择用户'); return }
  try {
    const updated: any = await platformApi.employee.updateUserPermissions(user.id, { permissions: permissionDraft.value })
    const next = Array.isArray(updated?.permissions) ? updated.permissions : permissionDraft.value
    user.permissions = next
    permissionDraft.value = [...next]
    notifySuccess('权限配置已保存')
  } catch (error) {
    notifyInfo(errorMessage(error, '权限配置接口尚未就绪'))
  }
}

// 员工列表「权限」按钮：跳到权限配置页并预选该员工（预选后 watch 会同步其真实权限）
function openPermissionConfig(userId: number) {
  permissionUserId.value = userId
  router.push('/app/' + role.value.toLowerCase() + '/permissions')
}

// 创建员工账号：打开弹窗并重置表单
function openCreateUser() {
  Object.assign(createUserForm, { real_name: '', username: '', phone: '', password: '', user_type: 'EMPLOYEE', department: '', employee_role: '' })
  createUserDialog.value = true
}

// 提交创建：POST /employee/users（MANAGER），成功后刷新员工列表，不做假成功
async function submitCreateUser() {
  if (createUserForm.real_name.trim().length < 2) { notifyInfo('请填写真实姓名（至少 2 个字）'); return }
  if (createUserForm.username.trim().length < 3) { notifyInfo('登录用户名至少 3 位'); return }
  if (createUserForm.password.length < 6) { notifyInfo('初始密码至少 6 位'); return }
  try {
    await platformApi.employee.createUser({
      real_name: createUserForm.real_name.trim(),
      username: createUserForm.username.trim(),
      password: createUserForm.password,
      user_type: createUserForm.user_type,
      phone: createUserForm.phone.trim() || undefined,
      department: createUserForm.department.trim() || undefined,
      employee_role: createUserForm.employee_role.trim() || undefined,
    })
    createUserDialog.value = false
    notifySuccess('账号已创建')
    try { employeeRows.value = itemsOf(await platformApi.employee.listUsers({ page: 1, page_size: 100 })) } catch { /* 列表刷新失败不影响创建结果 */ }
  } catch (error) {
    notifyInfo(errorMessage(error, '创建员工账号接口尚未就绪'))
  }
}

async function loadScoreRows() {
  try {
    const result: any = await platformApi.employee.listScores()
    scoreRows.value = itemsOf(result)
  } catch {}
}
async function loadDailyReports() {
  try {
    const result: any = await platformApi.employee.listReports()
    dailyReportRows.value = itemsOf(result)
  } catch {}
}
// v6.11.20：真实数据加载——审批 / 待补全线索
const pendingLeadRows = ref<any[]>([])
// MANAGER「流程审批」= 管理层全量待审批视图：/approvals/pending 是「待我审批」(按 approver_id 过滤)，
// 管理层账号通常不是被指派审批人，会导致列表恒空 → 改用 /employee/approvals-center 取 status==='pending' 子集
async function loadApprovals() {
  try {
    const result: any = await platformApi.employee.approvalsCenter({ page: 1, page_size: 50 })
    approvalRows.value = itemsOf(result).filter((item: any) => item.status === 'pending')
  } catch {}
}
async function loadPendingLeads() {
  try {
    const result: any = await platformApi.listPendingLeads({ page_size: 50 })
    pendingLeadRows.value = itemsOf(result)
  } catch {}
}
// merge v6.11.21：并入 master 差异字段——管理层看板 / 员工待办统计 / 学生心理 / 组织树
async function loadManagerOverview() {
  try { dashboardData.value = (await platformApi.employee.dashboard()) || {} } catch {}
  try { approvalsData.value = (await platformApi.employee.approvalsCenter({ page: 1, page_size: 20 })) || {} } catch {}
  try { employeeRows.value = itemsOf(await platformApi.employee.listUsers({ page: 1, page_size: 20 })) } catch {}
  const now = new Date()
  updatedAtLabel.value = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0')
}
async function loadEmployeeWorkspace() {
  try { todoRows.value = itemsOf(await platformApi.employee.listTodos({ page: 1, page_size: 10 })) } catch {}
  try { profileStats.value = (await platformApi.employee.profileStats()) || {} } catch {}
}
async function loadStudentProfile() {
  try {
    studentProfile.value = (await platformApi.student.psychProfile()) || {}
    if (typeof studentProfile.value.emotion_score === 'number') psychScore.value = studentProfile.value.emotion_score
  } catch {}
}
async function loadStudentWorkspace() {
  try { studentReminders.value = (await platformApi.student.reminders()) || {} } catch {}
  try { studentAcademic.value = (await platformApi.student.academic()) || {} } catch {}
  try { studentTickets.value = itemsOf(await platformApi.student.listTickets({ page: 1, page_size: 20 })) } catch {}
  try { lifeFaqRows.value = itemsOf(await platformApi.student.lifeFaq()) } catch {}
  try { moreServiceRows.value = itemsOf(await platformApi.student.moreServices()) } catch {}
  try { studentProgressRows.value = itemsOf(await platformApi.student.progress()) } catch { studentProgressRows.value = [] }
  try { studentLeaveRows.value = itemsOf(await platformApi.student.listAdminServices({ page: 1, page_size: 20 })).filter((item: any) => String(item?.service_type || '').includes('请假')) } catch { studentLeaveRows.value = [] }
}
async function loadOrgTree() {
  try { orgTree.value = itemsOf(await platformApi.employee.org()) } catch {}
}
async function loadOrgMembers() {
  try {
    orgMembers.value = itemsOf(await platformApi.employee.orgMembers({ keyword: orgKeyword.value.trim() || undefined, page: 1, page_size: 20 }))
  } catch { orgMembers.value = [] }
}
function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback
}

async function submitScoreConfirmed() {
  try {
    const result: any = await platformApi.employee.createScore({
      student_id: Number(scoreForm.studentId),
      course_name: scoreForm.courseName.trim(),
      score: Number(scoreForm.score),
      semester: scoreForm.semester.trim() ? scoreForm.semester.trim() : undefined,
    })
    scoreRows.value = [result, ...scoreRows.value]
    notifySuccess("成绩录入成功")
  } catch (error: unknown) {
    notifyInfo(errorMessage(error, "该学生、课程和学期已录入成绩，请使用编辑功能"))
  }
}

function submitScore() {
  const score = Number(scoreForm.score)
  if (!scoreForm.studentId) {
    ElMessage.warning("请输入学生 ID")
    return
  }
  if (!scoreForm.courseName.trim()) {
    ElMessage.warning("请输入课程名称")
    return
  }
  if (!Number.isFinite(score) || score < 0 || score > 100) {
    ElMessage.warning("请输入 0 到 100 之间的成绩")
    return
  }
  confirmWrite("确认录入该成绩吗？", submitScoreConfirmed)
}

async function editScore(row: any) {
  try {
    const result = await ElMessageBox.prompt("请输入新的成绩", "修改成绩", {
      inputValue: String(row.score),
      inputValidator: (value: string) => {
        const next = Number(value)
        return (Number.isFinite(next) && next >= 0 && next <= 100) || "请输入 0 到 100 之间的成绩"
      },
    })
    await platformApi.employee.updateScore(row.id, { score: Number(result.value) })
    await loadScoreRows()
    notifySuccess("成绩修改成功")
  } catch (error: unknown) {
    if (error === "cancel" || error === "close") return
    notifyInfo(errorMessage(error, "成绩修改失败"))
  }
}

function openDailyReport(row: any) {
  activeReport.value = row
  reportDialog.value = true
}

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
const drillNote = ref('')
const drillLoading = ref('')

function itemsOf(value: any): any[] {
  if (Array.isArray(value)) return value
  return value?.items || []
}

// 待办「处理」：此前按钮没有任何点击事件（纯装饰，点了没反应），现接后端 PUT /employee/todos/{id}
async function handleTodo(item: any) {
  if (!item || item.status === 'done') return
  confirmWrite('确认将「' + (item.title || '该待办') + '」标记为已完成吗？', async () => {
    try {
      const next: any = await platformApi.employee.updateTodo(item.id, { status: 'done' })
      item.status = next?.status || 'done'
      notifySuccess('已标记为已完成')
      try { reminders.value = await platformApi.employeeReminders() } catch { /* 统计卡刷新失败不影响处理结果 */ }
    } catch (error) {
      notifyInfo(errorMessage(error, '待办接口尚未就绪'))
    }
  })
}

// 关键操作日志（MANAGER）：此前是写死的「暂无操作日志（数据源待接入）」空状态
function operatorName(id?: number) {
  if (!id) return '—'
  const name = employeeName(id)
  return name === '—' ? '用户#' + id : name
}

async function loadOperationLogs() {
  try {
    operationLogRows.value = itemsOf(await platformApi.operationLogs({ page: 1, page_size: 20 }))
  } catch {
    operationLogRows.value = []
  }
}

// 消息中心：此前通知行是纯 div，点了没反应；后端 PUT /notifications/{id}/read 一直没接
async function markNotification(item: any) {
  if (!item || item.is_read) return
  try {
    await platformApi.markNotificationRead(item.id)
    item.is_read = true
    notifySuccess('已标记为已读')
  } catch (error) {
    notifyInfo(errorMessage(error, '通知接口尚未就绪'))
  }
}

async function markAllNotifications() {
  if (!notificationRows.value.length) return
  try {
    await platformApi.markAllNotificationsRead()
    notificationRows.value.forEach((item: any) => { item.is_read = true })
    notifySuccess('已全部标记为已读')
  } catch (error) {
    notifyInfo(errorMessage(error, '通知接口尚未就绪'))
  }
}

onMounted(async () => {
  try {
    // 公开列表（课程/活动）：走平台层，接口不可用时由平台层登记提示条
    platformApi.projects().then((rows) => { publicProjects.value = rows }).catch(() => {})
    platformApi.events().then((rows) => { publicEvents.value = rows }).catch(() => {})
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
  if (role.value === "EMPLOYEE") {
    await loadScoreRows()
    await loadDailyReports()
    await loadPendingLeads()
    await loadLeads()
  }
  if (role.value === 'MANAGER') {
    await loadApprovals()
    await loadOperationLogs()
  }
  if (role.value === 'PROSPECT') {
    loadConsultRows()
  }
  // 管理层：经营看板 + 审批中心；员工：待办与客户统计；两者：组织树；学生：心理画像（综合状态）
  if (role.value === 'MANAGER') await loadManagerOverview()
  if (role.value === 'EMPLOYEE') await loadEmployeeWorkspace()
  if (role.value === 'EMPLOYEE' || role.value === 'MANAGER') await loadOrgTree()
  if (role.value === 'EMPLOYEE') await loadOrgMembers()
  if (role.value === 'STUDENT') await loadStudentProfile()
  if (role.value === 'STUDENT') await loadStudentWorkspace()
  if (role.value === 'EMPLOYEE' || role.value === 'MANAGER') customerRows.value = customerRows.value.map(normalizeCustomer)
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

// ── v6.11.0 周期选择（自然周 / 自然月 / 指定月份） ──────────
const periodMode = ref<'last_week' | 'this_week' | 'this_month' | 'last_month' | 'custom_month'>('last_week')
const customMonth = ref<string>(new Date().toISOString().slice(0, 7))

function pad2(n: number): string { return String(n).padStart(2, '0') }

/** 计算请求周期（北京时间自然周/自然月，左闭右开），与后端 report_period 口径一致 */
function resolvePeriod(): { period_start?: string; period_end?: string } {
  const now = new Date()
  const monday = (d: Date) => {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diff = (x.getDay() + 6) % 7
    x.setDate(x.getDate() - diff)
    return x
  }
  const iso = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T00:00:00`
  if (periodMode.value === 'last_week') {
    const m = monday(now); const prev = new Date(m); prev.setDate(m.getDate() - 7)
    return { period_start: iso(prev), period_end: iso(m) }
  }
  if (periodMode.value === 'this_week') {
    const m = monday(now); const next = new Date(m); next.setDate(m.getDate() + 7)
    return { period_start: iso(m), period_end: iso(next) }
  }
  if (periodMode.value === 'this_month') {
    const s = new Date(now.getFullYear(), now.getMonth(), 1)
    const e = new Date(now.getFullYear(), now.getMonth() + 1, 1)
    return { period_start: iso(s), period_end: iso(e) }
  }
  if (periodMode.value === 'last_month') {
    const s = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    const e = new Date(now.getFullYear(), now.getMonth(), 1)
    return { period_start: iso(s), period_end: iso(e) }
  }
  // custom_month: YYYY-MM
  const [y, m] = customMonth.value.split('-').map(Number)
  if (!y || !m) return {}
  return {
    period_start: iso(new Date(y, m - 1, 1)),
    period_end: iso(new Date(y, m, 1)),
  }
}

function periodLabel(): string {
  const p = resolvePeriod()
  if (!p.period_start || !p.period_end) return '缺省周期（上一完整自然周）'
  return `${p.period_start.slice(0, 10)} ~ ${p.period_end.slice(0, 10)}`
}

function generateReport(type: string) {
  const period = resolvePeriod()
  confirmWrite(
    '确认生成「' + typeName(type) + '」（周期：' + periodLabel() + '）吗？重复生成同类型同周期会保留历史版本。',
    async () => {
      reportGenerating.value = type
      try {
        await platformApi.reports.generate({ report_type: type, ...period })
        notifySuccess('报告已生成')
        reportPage.value = 1
        await loadReports()
      } catch (error: any) {
        // 拦截器已提示业务错误；这里补状态呈现
        reportError.value = String(error?.message || '生成失败，请稍后重试')
      } finally {
        reportGenerating.value = ''
      }
    },
  )
}

// ── v6.11.0 历史版本（同类型同周期） ────────────────────────
const versionDialog = ref(false)
const versionLoading = ref(false)
const versionRows = ref<any[]>([])
const versionContext = ref<{ type: string; start: string; end: string } | null>(null)

async function openVersions(row: any) {
  versionContext.value = {
    type: row.report_type,
    start: String(row.time_range_start || ''),
    end: String(row.time_range_end || ''),
  }
  versionDialog.value = true
  versionLoading.value = true
  versionRows.value = []
  try {
    const res: any = await platformApi.reports.versions(
      row.report_type, String(row.time_range_start || ''), String(row.time_range_end || ''),
    )
    versionRows.value = itemsOf(res)
  } catch (error: any) {
    ElMessage.warning(String(error?.message || '历史版本加载失败'))
  } finally {
    versionLoading.value = false
  }
}

async function openVersion(row: any) {
  versionDialog.value = false
  await openReport(row)
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
  drillNote.value = ''
}

async function loadDrill(kind: 'customers' | 'psychCases' | 'specialCases') {
  if (!selectedReport.value) return
  drillLoading.value = kind
  drillNote.value = ''
  try {
    const data: any = await platformApi.reports[kind](selectedReport.value.id)
    drill.value[kind] = itemsOf(data)
    // v6.11.0：快照口径——历史报告无快照时后端给出提示，这里原样展示
    drillNote.value = String(data?.note || '')
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

/** AI 文字来源文案（v6.11.0：dify=报告专用 Agent / mock=演示模拟 / unavailable=不可用） */
function aiSourceText(content: any): string {
  if (!content || content.ai_status !== 'available') return 'AI 不可用，仅展示确定性指标'
  if (content.ai_source === 'dify') return '可用（报告专用 Agent）'
  if (content.ai_source === 'model') return '可用（共用模型网关）'
  if (content.ai_source === 'mock') return '可用（演示模拟数据）'
  return '可用'
}

/** 指标值渲染：null 一律显示「数据不可得」，不用 0 冒充（v6.11.0 §2.8） */
function metricValueText(value: any): string {
  if (value === null || value === undefined) return '数据不可得'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** 状态徽标：数据源 / 数据质量 / 不可得字段 / AI 可用性（v6.11.0 §2.8） */
function reportBadges(content: any): { label: string; type: string }[] {
  if (!content) return []
  const out: { label: string; type: string }[] = []
  const src = content.header?.data_source_status
  out.push({ label: src === 'production' ? '正式数据' : '演示数据', type: src === 'production' ? 'success' : 'warning' })
  const quality: any = content.data_quality || {}
  const failed = Object.entries(quality).filter(([, v]) => v === 'read_failed').map(([k]) => k)
  if (failed.length) out.push({ label: `读取失败：${failed.join('/')}`, type: 'danger' })
  const unavailable: any = content.data_unavailable || {}
  const fields = Object.values(unavailable).flat() as string[]
  if (fields.length) out.push({ label: `数据不可得：${fields.length} 项`, type: 'info' })
  const aiOk = content.ai_status === 'available'
  out.push({ label: aiOk ? aiSourceText(content) : 'AI 不可用', type: aiOk ? 'success' : 'info' })
  return out
}

/** 四类画像渲染（符合/部分符合/不符合/信息不足 + 分母） */
function profileRows(metrics: any): { key: string; value: string }[] {
  const rows: { key: string; value: string }[] = []
  const profiles = metrics?.profiles || {}
  const denom = metrics?.profile_denominator || {}
  for (const [attr, label] of [['sg_conclusion', '新加坡'], ['de_conclusion', '德国']] as const) {
    const item = profiles[attr]
    if (!item) {
      rows.push({ key: `${label}画像`, value: '数据不可得' })
      continue
    }
    const total = denom[attr]
    rows.push({
      key: `${label}画像（分母 ${total ?? '—'}）`,
      value: `符合 ${item['符合']} / 部分符合 ${item['部分符合']} / 不符合 ${item['不符合']} / 信息不足 ${item['信息不足']}`,
    })
  }
  return rows
}

/** 上一周期对比文案 */
function comparisonText(comp: any): string {
  if (!comp) return ''
  if (comp.status !== 'ok') return comp.note || '上一周期数据不可得，不做对比'
  const m = comp.metrics || {}
  const ov = m.status_overview || {}
  return `对比周期 ${String(comp.period_start || '').slice(0, 10)} ~ ${String(comp.period_end || '').slice(0, 10)}：`
    + `上期新增 ${metricValueText(m.new_this_period)} 名；上期期末意向 ${metricValueText(ov.intent)}、`
    + `成交 ${metricValueText(ov.converted)}、流失 ${metricValueText(ov.lost)}`
}

/** 心理个案历史记录合并展示 */
function historyText(history: any): string {
  if (!Array.isArray(history) || history.length === 0) return '—'
  return history
    .map((h: any) => `${String(h.record_at || '').slice(5, 16)} ${h.emotion_tag || ''}/${h.risk_level || ''}`)
    .join('；')
}

/** 展开层 metrics 为可渲染的键值行（一层嵌套展平） */
function metricRows(metrics: any): { key: string; value: any }[] {
  if (!metrics || typeof metrics !== 'object') return []
  const rows: { key: string; value: any }[] = []
  for (const [key, value] of Object.entries(metrics)) {
    if (key === 'profiles' || key === 'profile_denominator' || key === 'availability') continue
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

// 员工/状态筛选交由服务端（GET /employee/customers 支持 status / employee_id 参数），
// 避免只在前 N 条已加载数据里过滤导致「筛出来永远是空」；此处仅保留关键字本地过滤
const filteredCustomers = computed(() => customerRows.value.filter((item: any) =>
  (!keyword.value || item.name.includes(keyword.value) || item.phone.includes(keyword.value) || item.project.includes(keyword.value))
  && (customerStatusFilter.value === 'all' || customerStatusKey(item.status) === customerStatusFilter.value),
))

async function loadCustomers() {
  try {
    const page: any = await platformApi.employeeCustomers({
      page: 1,
      page_size: 100,
      status: customerStatusFilter.value === 'all' ? undefined : customerStatusFilter.value,
      employee_id: customerOwnerFilter.value === 'all' ? undefined : customerOwnerFilter.value,
    })
    customerRows.value = itemsOf(page).map(normalizeCustomer)
  } catch {
    notifyInfo('客户列表接口尚未就绪')
  }
}

watch([customerOwnerFilter, customerStatusFilter], () => { loadCustomers() })

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
  // 后端未提供删除跟进记录接口，不再返回假的“已删除”提示
  notifyInfo('删除跟进记录接口尚未开放，客户“' + (customer?.name || '') + '”的记录未被修改')
}

function submitLeave() {
  if (!leaveForm.start || !leaveForm.end || !leaveForm.reason) {
    ElMessage.warning('请补全请假信息')
    return
  }
  confirmWrite('确认提交请假申请吗？提交后将通知负责员工审批。', async () => {
    try {
      await platformApi.student.submitAdminService({
        service_type: '请假-' + leaveForm.type,
        start_time: leaveForm.start,
        end_time: leaveForm.end,
        reason: leaveForm.reason,
      })
      leaveDialog.value = false
      notifySuccess('请假申请已提交')
    } catch (error: unknown) {
      notifyInfo(errorMessage(error, '请假接口尚未就绪'))
    }
  })
}

function submitReport() {
  const reportDate = reportForm.date.trim()
  const content = reportForm.content.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(reportDate)) {
    ElMessage.warning('请输入有效的日报日期')
    return
  }
  if (!content) {
    ElMessage.warning('请输入日报内容')
    return
  }
  confirmWrite('确认提交日报吗？提交后将进入日报记录。', async () => {
    try {
      const created: any = await platformApi.employee.submitReport({
        report_date: reportDate,
        content,
        status: 'submitted',
      })
      dailyReportRows.value = [created, ...dailyReportRows.value]
      reportForm.content = ''
      notifySuccess('日报提交成功')
    } catch (error: unknown) {
      notifyInfo(errorMessage(error, '日报提交失败'))
    }
  })
}

function toggleApproval(id: number, checked: boolean) {
  if (checked) {
    if (!selectedApprovals.value.includes(id)) selectedApprovals.value.push(id)
  } else {
    selectedApprovals.value = selectedApprovals.value.filter((item) => item !== id)
  }
}

async function batchApprove() {
  if (!selectedApprovals.value.length) {
    notifyInfo('请先勾选需要批量通过的申请')
    return
  }
  try {
    await platformApi.approvals.batchApprove({ instance_ids: [...selectedApprovals.value], comment: '批量通过' })
    selectedApprovals.value = []
    await loadApprovals()
    notifySuccess('批量审批已完成')
  } catch {
    notifyInfo('批量审批失败，请稍后重试')
  }
}

async function approveItem(item: any) {
  try {
    await platformApi.approvals.approve(item.id, { comment: '同意' })
    approvalRows.value = approvalRows.value.filter((r: any) => r.id !== item.id)
    notifySuccess('已通过')
  } catch {
    notifyInfo('审批失败，请稍后重试')
  }
}

async function rejectItem(item: any) {
  try {
    await platformApi.approvals.reject(item.id, { comment: '请补充材料' })
    approvalRows.value = approvalRows.value.filter((r: any) => r.id !== item.id)
    notifySuccess('已驳回')
  } catch {
    notifyInfo('审批失败，请稍后重试')
  }
}

// v6.11.20：个人信息表单（替换写死的"陈顾问"假保存）
const profileForm = reactive({
  real_name: String(userStore.userInfo?.real_name || ''),
  contact_info: String(userStore.userInfo?.contact_info || ''),
})
async function saveEmployeeProfile() {
  try {
    await platformApi.users.updateMe({ real_name: profileForm.real_name, contact_info: profileForm.contact_info })
    notifySuccess('个人信息已保存')
  } catch {
    notifyInfo('个人信息保存失败，请稍后重试')
  }
}

// v6.11.20：PROSPECT 活动报名真调接口（原为假成功提示）+ 我的咨询本地回执
const consultRows = ref<any[]>([])
function loadConsultRows() {
  try {
    consultRows.value = JSON.parse(localStorage.getItem('my_consultations') || '[]')
  } catch {
    consultRows.value = []
  }
}
// v6.11.20：待补全线索合并为正式客户（pending_lead → customer）
async function mergePendingLeadRow(row: any) {
  try {
    const result = await ElMessageBox.prompt('合并为正式客户需要手机号（业务唯一键）', '合并待补全线索', {
      inputValue: '',
      inputValidator: (v: string) => /^\d{11,20}$/.test(v.trim()) || '请输入 11-20 位手机号',
    })
    await platformApi.mergePendingLead(row.id, { phone: result.value.trim(), name: row.name || undefined })
    await loadPendingLeads()
    notifySuccess('已合并为正式客户')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') notifyInfo('合并失败，请稍后重试')
  }
}

// v6.11.20：线索管理（GET /crm/leads + POST follow-ups + PATCH status）
const leadRows = ref<any[]>([])
async function loadLeads() {
  try {
    const result: any = await platformApi.listLeads({ page_size: 50 })
    leadRows.value = itemsOf(result)
  } catch {}
}
async function addLeadFollowUp(row: any) {
  try {
    const result = await ElMessageBox.prompt('输入跟进内容', '添加跟进 · ' + (row.name || row.phone || row.id), {
      inputType: 'textarea',
      inputValidator: (v: string) => !!v.trim() || '跟进内容不能为空',
    })
    await platformApi.leadAddFollowUp(row.id, { content: result.value.trim() })
    notifySuccess('跟进记录已添加')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') notifyInfo('添加跟进失败，请稍后重试')
  }
}
async function changeLeadStatus(row: any) {
  try {
    const result = await ElMessageBox.prompt('输入目标状态（new=新线索 / processing=跟进中 / converted=已转化 / invalid=无效）', '变更线索状态', {
      inputValue: row.status || 'processing',
    })
    await platformApi.leadChangeStatus(row.id, { status: result.value.trim() })
    await loadLeads()
    notifySuccess('状态已更新')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') notifyInfo('状态更新失败，请稍后重试')
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

async function changePassword() {
  try {
    const oldOne = await ElMessageBox.prompt('请输入当前密码', '修改密码', { inputType: 'password', inputValidator: (value: string) => (value ? true : '请输入当前密码') })
    const newOne = await ElMessageBox.prompt('请输入新密码（至少 6 位）', '修改密码', { inputType: 'password', inputValidator: (value: string) => (value && value.length >= 6 ? true : '新密码至少 6 位') })
    await platformApi.employee.changePassword({ old_password: oldOne.value, new_password: newOne.value })
    notifySuccess('密码已修改，请重新登录')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    notifyInfo(errorMessage(error, '密码修改接口尚未就绪'))
  }
}

async function applyEvent(event: any) {
  confirmWrite('确认报名“' + (event?.title || '该活动') + '”吗？', async () => {
    try {
      await platformApi.eventRegister(event.id)
      notifySuccess('报名成功')
    } catch (error: unknown) {
      notifyInfo(errorMessage(error, '活动报名接口尚未就绪'))
    }
  })
}

async function addFollowUp() {
  const customer = activeCustomer.value
  if (!customer?.id) {
    notifyInfo('请先选择客户')
    return
  }
  try {
    const input = await ElMessageBox.prompt('请输入本次跟进内容', '添加跟进记录', {
      inputPlaceholder: '例如：已电话沟通，家长关注新加坡项目费用',
      inputValidator: (value: string) => (value && value.trim() ? true : '请输入跟进内容'),
    })
    await platformApi.employee.createFollowUp({ customer_id: customer.id, content: input.value.trim() })
    notifySuccess('跟进记录已添加')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    notifyInfo(errorMessage(error, '跟进接口尚未就绪'))
  }
}

function employeeName(id?: number) {
  if (!id) return '—'
  const fromAccounts = employeeRows.value.find((item: any) => item.id === id)
  if (fromAccounts?.real_name) return fromAccounts.real_name
  const fromMembers = orgMembers.value.find((item: any) => item.user_id === id)
  return fromMembers?.real_name || '—'
}

// 后端 /employee/customers 返回 recommended/assessment_score/owner_employee_id/last_follow_at，
// 与页面列名（project/score/owner/last）不一致，这里统一映射，避免四列空白；
// 降级 mock 数据没有这些后端字段，原样返回不改动
function normalizeCustomer(raw: any) {
  if (!raw || (raw.owner_employee_id === undefined && raw.assessment_score === undefined && raw.last_follow_at === undefined && raw.recommended === undefined)) return raw
  const rec = raw.recommended
  let project = '—'
  if (typeof rec === 'string') project = rec
  else if (Array.isArray(rec)) project = rec.map((item: any) => item?.project_name || item?.name || String(item)).filter(Boolean).join('、') || '—'
  else if (rec && typeof rec === 'object') project = rec.project_name || rec.name || '—'
  return {
    ...raw,
    project,
    score: raw.assessment_score === null || raw.assessment_score === undefined ? '—' : raw.assessment_score,
    owner: employeeName(raw.owner_employee_id),
    last: raw.last_follow_at ? String(raw.last_follow_at).slice(0, 10) : '—',
  }
}

function onCustomerSelection(rows: any[]) {
  selectedCustomerIds.value = rows.map((row: any) => row.id)
}

function openReassign(customer: any) {
  reassignCustomer.value = customer
  reassignDialogTargetId.value = undefined
  reassignDialog.value = true
}

async function doReassign(fromId: number, toId: number, customerIds: number[]) {
  try {
    const result: any = await platformApi.employee.reassignCustomers({
      from_employee_id: fromId,
      to_employee_id: toId,
      customer_ids: customerIds,
    })
    notifySuccess('已转移 ' + (result?.moved ?? customerIds.length) + ' 个客户')
    return true
  } catch (error: unknown) {
    notifyInfo(errorMessage(error, '客户再分配接口尚未就绪'))
    return false
  }
}

async function confirmReassign() {
  if (!reassignDialogTargetId.value) {
    ElMessage.warning('请选择目标员工')
    return
  }
  const fromId = reassignCustomer.value?.owner_employee_id
  if (!fromId) {
    notifyInfo('该客户当前没有归属员工，无法变更归属')
    return
  }
  if (await doReassign(fromId, reassignDialogTargetId.value, [reassignCustomer.value.id])) {
    reassignDialog.value = false
  }
}

async function batchReassign() {
  if (!selectedCustomerIds.value.length) {
    ElMessage.warning('请先勾选需要再分配的客户')
    return
  }
  if (!reassignFromId.value || !reassignToId.value) {
    ElMessage.warning('请选择原归属员工和目标员工')
    return
  }
  await doReassign(reassignFromId.value, reassignToId.value, selectedCustomerIds.value)
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

function revealPhone(member: any) {
  confirmWrite('确认查看 ' + (member.real_name || '该同事') + ' 的完整手机号吗？该敏感操作会写入操作日志。', async () => {
    try {
      const data: any = await platformApi.employee.revealPhone(member.user_id)
      revealedPhones.value[member.user_id] = data?.phone || '—'
      notifySuccess('完整号码：' + (data?.phone || '—'))
    } catch (error: unknown) {
      notifyInfo(errorMessage(error, '接口尚未就绪'))
    }
  })
}
</script>

<template>
  <div class="workspace">
    <el-alert v-if="fallbackState.keys.length" class="fallback-banner" type="warning" :closable="false" show-icon :title="'接口不可用，以下内容为演示数据：' + fallbackState.keys.join('、')" />
    <SectionTitle :eyebrow="role" :title="pageTitle" desc="数据按业务模块和接口口径展示。">
    </SectionTitle>

    <template v-if="section === 'home' && role === 'STUDENT'">
      <section class="welcome surface"><div><span class="badge">STUDENT · 德国双元制护理</span><h2>{{ userStore.userInfo?.real_name || '同学' }}，欢迎回来</h2><p>负责顾问：— · 语言班进度：— · 当前状态：—</p></div><div class="welcome-score"><small>综合状态</small><strong>{{ studentProfile.emotion_score ?? '—' }}</strong><span>{{ studentProfile.latest_emotion_tag || '暂无评估' }}</span></div></section>
      <div class="stat-grid"><StatCard label="待办事项" :value="String(studentReminderTotal)" note="学业与服务提醒" tone="coral" /><StatCard label="本周课程" value="—" tone="purple" /><StatCard label="申请进度" :value="studentProgressCurrent?.stage || '—'" :note="progressStatusText(studentProgressCurrent) || '暂无进度记录'" tone="lime" /><StatCard label="服务状态" value="—" tone="amber" /></div>
      <div class="two-column">
        <section class="surface panel"><SectionTitle title="近期课程与 DDL" /><div v-for="(item, index) in studentDdlRows" :key="item.title" class="task-row"><b>0{{ index + 1 }}</b><div><strong>{{ item.title }}</strong><small>{{ item.due }}</small></div><el-tag :type="item.tone === 'coral' ? 'danger' : item.tone === 'amber' ? 'warning' : 'primary'">{{ item.due }}</el-tag></div><el-empty v-if="!studentDdlRows.length" description="暂无近期课程与 DDL" /></section>
        <section class="surface panel student-progress-panel"><SectionTitle title="留学申请进度" /><el-steps v-if="studentProgressSteps.length" class="student-progress-steps" direction="vertical" :active="studentProgressSteps.length - 1" size="small" :space="58"><el-step v-for="item in studentProgressSteps" :key="item.stage" :title="item.stage" :description="progressStatusText(item)" /></el-steps><el-empty v-else description="暂无申请进度" /></section>
      </div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'admin'">
      <div class="two-column">
        <section class="surface panel"><SectionTitle title="提交请假申请" desc="支持页面提交，也可以直接使用学生助手代办。" /><el-form label-position="top"><div class="form-grid"><el-form-item label="请假类型"><el-select v-model="leaveForm.type" style="width:100%"><el-option v-for="item in ['事假','病假','考试假','其他']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="开始日期"><el-input v-model="leaveForm.start" placeholder="2026-10-18" /></el-form-item><el-form-item label="结束日期"><el-input v-model="leaveForm.end" placeholder="2026-10-20" /></el-form-item><el-form-item label="预计缺课"><el-input placeholder="3节" /></el-form-item></div><el-form-item label="请假事由"><el-input v-model="leaveForm.reason" type="textarea" :rows="4" /></el-form-item><el-button type="primary" size="large" @click="submitLeave">提交请假申请</el-button></el-form></section>
        <section class="surface panel"><SectionTitle title="申请状态" /><div v-for="item in studentLeaveRows" :key="item.id" class="ticket-row"><div><b>{{ item.service_type || '请假申请' }}</b><small>{{ String(item.create_time || '').slice(0, 10) || '—' }}</small></div><el-tag :type="item.status === '已通过' ? 'success' : item.status === '已拒绝' ? 'danger' : 'warning'">{{ item.status || '待审批' }}</el-tag></div><el-empty v-if="!studentLeaveRows.length" description="暂无请假申请" /></section>
      </div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'psych'">
      <section class="psych-hero surface"><div><span class="badge">AI 对话式评估 · 一期</span><h2>今日心理状态</h2><p>服务性综合状态评分，不构成医疗诊断。</p></div><div class="score-ring"><strong>{{ psychScore }}</strong><span>/ 100</span><small>{{ studentProfile.latest_emotion_tag || '暂无评估' }}</small></div></section>
      <div class="two-column"><section class="surface panel"><SectionTitle title="情绪趋势" desc="近 7 日评估记录的综合状态变化" /><div v-if="emotionTrendPoints" class="line-chart"><div class="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span></div><div class="chart-area"><svg viewBox="0 0 600 220" preserveAspectRatio="none"><polyline :points="emotionTrendPoints" fill="none" stroke="#5a50b8" stroke-width="8" stroke-linecap="round" /></svg></div></div><el-empty v-else description="暂无情绪趋势数据" /></section><section class="surface panel"><SectionTitle title="服务边界" /><ul class="boundary"><li>不提供医疗级心理建议或诊断</li><li>不承诺退费、转学等重大决定</li><li>遇到严重问题，引导联系专业心理咨询师</li><li>识别到高风险会即时通知负责员工</li></ul><el-button type="primary" round @click="startPsychChat">开始一次情绪对话</el-button><p v-if="studentProfile.latest_emotion_tag" class="muted">最近标签：{{ studentProfile.latest_emotion_tag }}</p></section></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'feedback'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="提交反馈工单" desc="普通咨询和建议不会计入投诉周报。" /><el-form label-position="top"><el-form-item label="反馈类型"><el-select style="width:100%" v-model="ticketForm.type"><el-option v-for="item in ['服务咨询','课程安排','费用问题','住宿生活','投诉建议']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="问题标题"><el-input v-model="ticketForm.title" placeholder="请简要描述问题" /></el-form-item><el-form-item label="详细描述"><el-input v-model="ticketForm.detail" type="textarea" :rows="5" /></el-form-item><el-checkbox v-model="ticketForm.formal">确认这是正式投诉（仅正式投诉进入投诉周报）</el-checkbox><el-button type="primary" style="margin-top:18px" @click="submitTicket">提交工单</el-button></el-form></section><section class="surface panel"><SectionTitle title="我的工单" /><div v-for="item in studentTickets" :key="item.id" class="ticket-row"><div><b>{{ item.content }}</b><small>{{ String(item.create_time || '').slice(0, 10) || '—' }}</small></div><el-tag :type="item.status === '已解决' ? 'success' : 'warning'">{{ item.status }}</el-tag></div><el-empty v-if="!studentTickets.length" description="暂无工单" /></section></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'academic'">
      <div class="stat-grid"><StatCard label="7日内到期" :value="String(studentAcademicStats.due7d)" tone="coral" /><StatCard label="待提交作业" :value="String(studentAcademicStats.pending)" tone="amber" /><StatCard label="当前 GPA" :value="studentAcademicStats.gpa" :note="'共 ' + studentAcademicStats.scoreCount + ' 门课程'" tone="lime" /><StatCard label="系统已推送" :value="String(studentAcademicStats.pushed)" :note="'到期提醒由系统自动发出'" tone="purple" /></div>
      <section class="surface panel"><SectionTitle title="DDL 与考试安排" /><div v-for="item in studentAcademicItems" :key="item.id" class="academic-row"><el-tag :type="item.item_type === '考试' ? 'danger' : item.item_type === '作业' ? 'warning' : 'info'">{{ item.item_type }}</el-tag><div><b>{{ item.title }}</b><small>截止时间 {{ String(item.due_time || '').slice(0, 10) || '—' }}</small></div><el-button text type="primary">查看详情</el-button></div><el-empty v-if="!studentAcademicItems.length" description="暂无 DDL 与考试安排" /></section>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'progress'">
      <section class="surface panel"><SectionTitle title="留学申请进度追踪" desc="阶段与备注由负责员工更新，展示真实进度记录。" /><el-steps v-if="studentProgressSteps.length" :active="studentProgressSteps.length - 1" align-center><el-step v-for="item in studentProgressSteps" :key="item.stage" :title="item.stage" /></el-steps><div v-if="studentProgressCurrent" class="progress-note"><b>当前阶段：{{ studentProgressCurrent.stage }}</b><p>{{ studentProgressCurrent.notes || '暂无备注' }}</p></div><el-empty v-else description="暂无申请进度记录" /></section>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'life'">
      <div class="life-grid"><article v-for="item in lifeFaqRows" :key="item.question" class="surface life-card"><h3>{{ item.question }}</h3><p>{{ item.answer }}</p><el-button text type="primary">查看指南</el-button></article><el-empty v-if="!lifeFaqRows.length" description="暂无生活指南" /></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'more'">
      <SectionTitle title="更多服务" desc="以下服务均为可选项目，不影响你已有的常规服务权益。" />
      <div class="service-grid"><article v-for="item in moreServiceRows" :key="item.code" class="surface service-card"><div class="service-icon">+</div><h3>{{ item.name }}</h3><p>{{ item.description }}</p><el-button round>了解详情</el-button></article><el-empty v-if="!moreServiceRows.length" description="暂无更多服务" /></div>
    </template>

    <template v-else-if="role === 'STUDENT' && section === 'profile'">
      <section class="surface profile-card"><SectionTitle title="账号资料" /><el-form label-position="top"><div class="form-grid"><el-form-item label="姓名"><el-input v-model="profileForm.real_name" /></el-form-item><el-form-item label="联系方式"><el-input v-model="profileForm.contact_info" /></el-form-item><el-form-item label="账号"><el-input :model-value="userStore.userInfo?.username || '—'" disabled /></el-form-item><el-form-item label="角色"><el-input :model-value="userStore.userInfo?.user_type || '—'" disabled /></el-form-item></div><el-button type="primary" @click="confirmWrite('确认保存个人信息修改吗？', saveEmployeeProfile)">保存修改</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'home'">
      <section class="welcome surface"><div><span class="badge">EMPLOYEE · {{ userStore.userInfo?.department || '—' }}</span><h2>{{ userStore.userInfo?.real_name || '员工' }}，上午好</h2><p>今日有 {{ reminders.todos_pending ?? 0 }} 项待办，{{ reminders.follow_ups_due ?? 0 }} 项待跟进，当前视图仅显示归属本人的数据。</p></div><el-button type="primary" round @click="customerDialog = true"><el-icon><Plus /></el-icon>录入新客户</el-button></section>
      <div class="stat-grid"><StatCard label="今日待办" :value="String(reminders.todos_pending ?? 0)" note="未完成待办" tone="coral" /><StatCard label="名下客户" :value="String(profileStats.total ?? customerRows.length)" :note="'本月新增 ' + (profileStats.month_new ?? 0)" tone="purple" /><StatCard label="跟进中 / 已转化" :value="(profileStats.following ?? 0) + ' / ' + (profileStats.signed ?? 0)" :note="'已流失 ' + (profileStats.lost ?? 0)" tone="lime" /><StatCard label="待我审批" :value="String(reminders.admin_services_pending ?? 0)" note="待审批行政服务" tone="amber" /></div>
      <div class="quick-grid"><button v-for="item in employeeMenu" :key="item.label" @click="item.action"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><el-icon><ArrowRight /></el-icon></button></div>
      <div class="two-column"><section class="surface panel"><SectionTitle title="今日待办" /><div v-for="item in todoRows.slice(0, 5)" :key="item.id" class="task-row"><b>!</b><div><strong>{{ item.title }}</strong><small>{{ todoStatusLabel[item.status] || item.status }} · 优先级{{ todoPriorityLabel[item.priority] || item.priority }}</small></div><el-button text type="primary" :disabled="item.status === 'done'" @click="handleTodo(item)">{{ item.status === 'done' ? '已完成' : '处理' }}</el-button></div><el-empty v-if="!todoRows.length" description="暂无待办" /></section><section class="surface panel"><SectionTitle title="客户跟进提醒" /><div v-if="reminders.follow_ups_due" class="task-row"><b>!</b><div><strong>今日应跟进 {{ reminders.follow_ups_due }} 位客户</strong><small>待跟进明细接口尚未开放，可到「客户经营」按最后跟进时间筛选</small></div></div><el-empty v-else description="今日暂无待跟进客户" /></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'customers'">
      <SectionTitle title="我的客户" desc="普通员工只能查看自己名下的客户，管理层可查看全域数据。"><el-button type="primary" :icon="Plus" @click="customerDialog = true">录入客户</el-button></SectionTitle>
      <div class="toolbar surface"><el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索姓名、手机号或项目" clearable /><el-button :icon="Download" @click="exportCsv('客户列表')">导出 CSV</el-button></div>
      <section class="surface table-card"><el-table :data="filteredCustomers" @row-click="(row:any) => activeCustomer = row"><el-table-column prop="name" label="客户" width="130" /><el-table-column prop="phone" label="手机号" width="130" /><el-table-column prop="project" label="意向项目" /><el-table-column prop="score" label="研判结论" width="110"><template #default="{ row }"><el-tag :type="row.score === '符合' ? 'success' : row.score === '待确认' ? 'warning' : 'info'">{{ row.score }}</el-tag></template></el-table-column><el-table-column prop="status" label="状态" width="110" /><el-table-column prop="owner" label="跟进人" width="100" /><el-table-column prop="last" label="最后跟进" width="100" /><el-table-column label="操作" width="180"><template #default="{ row }"><el-button text type="primary" @click.stop="activeCustomer = row">详情</el-button><el-button text type="danger" :icon="Delete" @click.stop="removeCustomer(row)" /></template></el-table-column></el-table></section>
      <section class="surface panel" style="margin-top:20px"><SectionTitle title="待补全线索" desc="访客项目咨询记录（pending_lead），补充手机号后可合并为正式客户" /><el-table :data="pendingLeadRows"><el-table-column prop="name" label="姓名" width="120" /><el-table-column prop="wechat" label="微信" width="130" /><el-table-column prop="raw_info" label="原始信息" /><el-table-column prop="status" label="状态" width="100" /><el-table-column label="操作" width="120"><template #default="{ row }"><el-button v-if="row.status !== 'merged' && !row.merged_customer_id" text type="primary" @click="mergePendingLeadRow(row)">合并</el-button><el-tag v-else size="small" type="success">已合并</el-tag></template></el-table-column></el-table><el-empty v-if="!pendingLeadRows.length" description="暂无待补全线索" /></section>
      <section class="surface panel" style="margin-top:20px"><SectionTitle title="线索管理" desc="CRM 线索跟进与状态流转（GET /crm/leads）" /><el-table :data="leadRows"><el-table-column prop="name" label="姓名" width="110"><template #default="{ row }">{{ row.name || '—' }}</template></el-table-column><el-table-column prop="phone" label="手机号" width="130"><template #default="{ row }">{{ row.phone || row.wechat || '—' }}</template></el-table-column><el-table-column prop="status" label="状态" width="110" /><el-table-column prop="source_channel" label="来源" width="110"><template #default="{ row }">{{ row.source_channel || '—' }}</template></el-table-column><el-table-column label="操作" width="200"><template #default="{ row }"><el-button text type="primary" @click="addLeadFollowUp(row)">添加跟进</el-button><el-button text @click="changeLeadStatus(row)">变更状态</el-button></template></el-table-column></el-table><el-empty v-if="!leadRows.length" description="暂无线索" /></section>
      <el-drawer v-model="activeCustomer" title="客户详情" size="min(620px, 94vw)"><template v-if="activeCustomer"><div class="customer-head"><div><h2>{{ activeCustomer.name }}</h2><p>{{ activeCustomer.project }} · {{ activeCustomer.phone }}</p></div><el-tag type="success">{{ activeCustomer.score }}</el-tag></div><h3>研判结果</h3><div class="assessment"><div><small>新加坡项目</small><b>{{ activeCustomer.score }}</b><p>学历、年龄和目标方向已形成初步匹配，缺失信息已列入跟进建议。</p></div><div><small>中德项目</small><b>待确认</b><p>德语能力、封闭实训接受度和无犯罪记录需要电话核实。</p></div></div><h3>推荐项目</h3><el-tag v-for="item in ['新加坡国际本硕升学计划','中德精英人才共建计划']" :key="item" class="recommend">{{ item }}</el-tag><h3>跟进记录</h3><el-timeline><el-timeline-item>官网注册留资 · 2026-10-13</el-timeline-item><el-timeline-item>Agent 自动采集 · 2026-10-13</el-timeline-item><el-timeline-item>员工首次跟进 · 2026-10-14</el-timeline-item></el-timeline><div class="drawer-actions"><el-button type="primary" @click="confirmWrite('确认添加一条跟进记录吗？', () => notifySuccess('跟进记录已添加'))">添加跟进</el-button><el-button @click="confirmWrite('确认更新客户状态吗？', () => notifySuccess('状态已更新'))">更新状态</el-button></div></template></el-drawer>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'scores'">
      <div class="two-column">
        <section class="surface panel"> <SectionTitle title="成绩录入" desc="每个学生、课程和学期只保留一条成绩。" />
          <el-form label-position="top">
            <el-form-item label="学生 ID"> <el-input-number v-model="scoreForm.studentId" :min="1" /> </el-form-item>
            <el-form-item label="学期"> <el-input v-model="scoreForm.semester" /> </el-form-item>
            <el-form-item label="课程名称"> <el-input v-model="scoreForm.courseName" /> </el-form-item>
            <el-form-item label="成绩"> <el-input-number v-model="scoreForm.score" :min="0" :max="100" :precision="1" /> </el-form-item>
            <el-button type="primary" @click="submitScore">保存成绩</el-button>
          </el-form> </section>
        <section class="surface panel"> <SectionTitle title="已录入成绩" />
          <el-table :data="scoreRows">
            <el-table-column prop="student_id" label="学生 ID" width="100" />
            <el-table-column prop="course_name" label="课程名称" />
            <el-table-column prop="semester" label="学期" width="110" />
            <el-table-column prop="score" label="成绩" width="90" />
            <el-table-column label="操作" width="100"> <template #default="{ row }"> <el-button text type="primary" @click="editScore(row)">编辑</el-button> </template> </el-table-column>
          </el-table> </section>
      </div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'convert'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="代客申请留学生" desc="一次审批：员工申请，管理层审批。" /><el-form label-position="top"><el-form-item label="选择意向客户"><el-select v-model="convertForm.customerId" style="width:100%"><el-option v-for="item in customerRows" :key="item.id" :label="item.name + '（' + item.project + '）'" :value="item.id" /></el-select></el-form-item><el-form-item label="转化项目"><el-select v-model="convertForm.project" style="width:100%"><el-option v-for="item in publicProjects.slice(0,3)" :key="item.id" :label="item.title" :value="item.title" /></el-select></el-form-item><el-form-item label="转化理由 / 备注"><el-input v-model="convertForm.title" type="textarea" :rows="4" /></el-form-item><el-button type="primary" @click="submitConvertApply">提交审批申请</el-button></el-form></section><section class="surface panel"><SectionTitle title="学生流程审批" /><div v-for="item in approvalRows" :key="item.id" class="ticket-row"><div><b>{{ item.title || '—' }}</b><small>学生端提交 · {{ String(item.created_at || '').slice(0, 10) || '—' }}</small></div><el-tag :type="item.status === 'approved' ? 'success' : 'warning'">{{ item.status || '—' }}</el-tag></div><el-empty v-if="!approvalRows.length" description="暂无学生流程审批" /></section></div>
    </template>

<template v-else-if="role === 'EMPLOYEE' && section === 'reports'">
<div class="two-column">
<section class="surface panel"> <SectionTitle title="提交日报" desc="提交后可在右侧查看历史记录。" />
<el-form label-position="top"> <el-form-item label="日报日期"> <el-input v-model="reportForm.date" /> </el-form-item>
<el-form-item label="日报内容"> <el-input v-model="reportForm.content" type="textarea" :rows="10" /> </el-form-item>
<el-button type="primary" @click="submitReport">确认提交</el-button> </el-form> </section>
<section class="surface panel"> <SectionTitle title="日报记录" />
<div v-for="item in dailyReportRows" :key="item.id" class="task-row"> <b>✓</b> <div> <strong>{{ item.report_date }}</strong> <small>{{ item.status }}</small> </div> <el-button text @click="openDailyReport(item)">查看</el-button> </div>
<el-empty v-if="!dailyReportRows.length" description="暂无日报" />
</section> </div>
<el-drawer v-model="reportDialog" title="日报详情" size="min(620px, 94vw)"> <template #default>
<div v-if="activeReport"> <h2>{{ activeReport.report_date }}</h2> <p>{{ activeReport.content }}</p> </div>
</template> </el-drawer> </template>
    <template v-else-if="role === 'EMPLOYEE' && section === 'org'">
      <div class="two-column"><section class="surface panel"><SectionTitle title="组织架构查询" desc="联系方式默认脱敏，查看完整号码需要二次确认。" /><el-tree :data="orgTree" :props="orgTreeProps" default-expand-all /><el-empty v-if="!orgTree.length" description="暂无组织数据" /><SectionTitle title="同事联系方式" desc="按姓名搜索，默认脱敏；查看完整号码需二次确认并记入操作日志。" /><el-input v-model="orgKeyword" :prefix-icon="Search" placeholder="搜索同事姓名" clearable @keyup.enter="loadOrgMembers" @clear="loadOrgMembers" /><el-button type="primary" @click="loadOrgMembers">搜索</el-button><div v-for="member in orgMembers" :key="member.user_id" class="task-row"><b>{{ (member.real_name || '?').slice(0, 1) }}</b><div><strong>{{ member.real_name }}</strong><small>{{ member.department || '—' }} · {{ revealedPhones[member.user_id] || member.phone_masked || '—' }}</small></div><el-button text type="primary" @click="revealPhone(member)">查看完整号码</el-button></div><el-empty v-if="!orgMembers.length" description="暂无同事数据" /></section><section class="surface panel"><SectionTitle title="新人指引" /><div v-for="item in ['办公环境快速导航','IT支持与设备使用','团队协作与沟通','公司文化与价值观','新人成长与资源支持']" :key="item" class="task-row"><b>0{{ item.length % 4 + 1 }}</b><div><strong>{{ item }}</strong><small>知识库 + 引导式流程</small></div><el-button text type="primary">打开</el-button></div></section></div>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'todos'">
      <div class="stat-grid"><StatCard label="待办事项" :value="String(reminders.todos_pending ?? 0)" tone="amber" /><StatCard label="待跟进" :value="String(reminders.follow_ups_due ?? 0)" tone="coral" /><StatCard label="待审批" :value="String(reminders.admin_services_pending ?? 0)" tone="purple" /><StatCard label="心理预警" :value="String(reminders.psych_alerts_pending ?? 0)" tone="lime" /></div>
      <section class="surface panel"><SectionTitle title="待办与消息" /><div v-for="item in todoRows" :key="item.id" class="task-row"><b>!</b><div><strong>{{ item.title }}</strong><small>{{ todoStatusLabel[item.status] || item.status }} · 优先级{{ todoPriorityLabel[item.priority] || item.priority }}</small></div><el-button text type="primary" :disabled="item.status === 'done'" @click="handleTodo(item)">{{ item.status === 'done' ? '已完成' : '处理' }}</el-button></div><el-empty v-if="!todoRows.length" description="暂无待办" /></section>
    </template>

    <template v-else-if="role === 'EMPLOYEE' && section === 'profile'">
      <section class="surface profile-card"><SectionTitle title="账号资料" /><el-form label-position="top"><div class="form-grid"><el-form-item label="姓名"><el-input :model-value="userStore.userInfo?.real_name || '—'" /></el-form-item><el-form-item label="手机号"><el-input :model-value="userStore.userInfo?.username || '—'" /></el-form-item><el-form-item label="部门"><el-input :model-value="userStore.userInfo?.department || '—'" /></el-form-item><el-form-item label="企业微信"><el-input :model-value="userStore.userInfo?.contact_info || '—'" /></el-form-item></div><el-button type="primary" @click="confirmWrite('确认保存个人信息修改吗？', saveEmployeeProfile)">保存修改</el-button><el-button @click="changePassword">修改密码</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'home'">
      <section class="welcome surface">
        <div>
          <span class="badge">MANAGER · 全域权限</span>
          <h2>经营看板概览</h2>
          <p>覆盖全域客户经营、业绩概览、销售漏斗和管理待办，数据按现有业务模块口径展示。</p>
        </div>
        <el-tag type="success">数据更新于 {{ updatedAtLabel }}</el-tag>
      </section>

      <div class="stat-grid">
        <StatCard label="新增意向数" :value="String(mgrOverview.new_prospects_this_month ?? '—')" :note="'其中仍意向 ' + (mgrOverview.new_outcomes?.intent ?? 0) + ' · 已签约 ' + (mgrOverview.new_outcomes?.signed ?? 0)" tone="purple" />
        <StatCard label="转化率" :value="(mgrOverview.conversion_rate ?? '—') + '%'" :note="'成交 ' + (mgrOverview.converted ?? 0) + ' / 客户 ' + (mgrCustomers.total ?? 0)" tone="lime" />
        <StatCard label="签约金额" value="暂无数据" note="签约金额数据源待接入" tone="amber" />
        <StatCard label="在办学生数" :value="String(mgrOverview.active_students ?? '—')" note="状态正常的在读学生" tone="coral" />
        <StatCard label="投诉率" :value="(mgrOverview.complaint_rate ?? '—') + '%'" :note="'待处理工单 ' + (dashboardData.tickets?.pending ?? 0)" tone="purple" />
        <StatCard label="待我审批" :value="String(mgrPendingTotal)" note="含转化、请假和员工流程" tone="coral" />
      </div>

      <div class="manager-dashboard-grid">
        <section class="surface panel funnel-panel">
          <SectionTitle title="全域客户转化漏斗" desc="从访客触达到成功转化的全域数据，可下钻到对应客户名单。" />
          <div class="funnel">
            <div v-for="item in funnelRows" :key="item.n" :style="{ width: item.p + '%' }">
              <b>{{ item.n }}</b><span>{{ item.v }}</span>
            </div>
            <el-empty v-if="!funnelRows.length" description="暂无数据" />
          </div>
          <div class="funnel-foot"><span>本月数据</span><span>异常环节会触发预警</span></div>
        </section>

        <section class="surface panel">
          <SectionTitle title="客户来源渠道分布" desc="按客户注册来源统计，反映各获客渠道贡献。" />
          <div v-for="item in sourceRows" :key="item.n" class="performance-row">
            <div><b>{{ item.n }}</b><span>{{ item.v }}</span></div>
            <el-progress :percentage="item.p" :show-text="false" />
          </div>
          <el-empty v-if="!sourceRows.length" description="暂无数据" />
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
          <el-empty description="暂无数据" />
        </section>
      </div>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'reports'">
      <!-- v6.11.0：列表 → 周期选择 → 生成 → 历史版本 → 详情 → 下钻（快照） → PDF -->
      <template v-if="!selectedReport">
        <div class="toolbar surface">
          <el-select v-model="reportFilterType" clearable placeholder="全部报告类型" style="width:200px" @change="reportPage = 1; loadReports()">
            <el-option v-for="t in REPORT_TYPES" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
          <el-select v-model="periodMode" style="width:190px">
            <el-option label="上一完整自然周" value="last_week" />
            <el-option label="本周（未结束）" value="this_week" />
            <el-option label="本月（未结束）" value="this_month" />
            <el-option label="上一自然月" value="last_month" />
            <el-option label="指定月份" value="custom_month" />
          </el-select>
          <el-date-picker
            v-if="periodMode === 'custom_month'"
            v-model="customMonth"
            type="month"
            value-format="YYYY-MM"
            placeholder="选择月份"
            style="width:150px"
          />
          <span class="muted">生成周期：{{ periodLabel() }}</span>
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
              <el-table-column label="操作" width="160">
                <template #default="{ row }">
                  <el-button text type="primary" @click.stop="openReport(row)">详情</el-button>
                  <el-button text @click.stop="openVersions(row)">历史版本</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination v-model:current-page="reportPage" :page-size="reportPageSize" :total="reportTotal" layout="prev, pager, next, total" @current-change="loadReports" style="margin:14px 0 4px; justify-content:flex-end" />
          </template>
        </section>
        <section class="surface panel" style="margin-top:20px">
          <SectionTitle title="手动生成报告" desc="一期为手动生成，无自动调度；重复生成同类型同周期保留历史版本，不覆盖旧版本。" />
          <div class="report-gen-grid">
            <button v-for="t in REPORT_TYPES" :key="t.type" class="report-gen-card" :disabled="reportGenerating !== ''" @click="generateReport(t.type)">
              <b>{{ t.code }}</b><strong>{{ t.name }}</strong><small>{{ t.period }}</small>
              <el-tag v-if="reportGenerating === t.type" size="small" type="info">生成中…</el-tag>
            </button>
          </div>
        </section>
      </template>

      <template v-else>
        <div class="toolbar surface" style="align-items:center; flex-wrap:wrap; gap:8px">
          <el-button @click="backToReportList">← 返回列表</el-button>
          <b style="font-size:16px">{{ selectedReport.report_title || typeName(selectedReport.report_type) }}</b>
          <el-tag
            v-for="badge in reportBadges(selectedReport.report_content)"
            :key="badge.label"
            :type="badge.type as any"
            size="small"
          >{{ badge.label }}</el-tag>
          <el-tag type="info" size="small">V{{ selectedReport.version }}</el-tag>
          <el-button style="margin-left:auto" :icon="Download" type="primary" @click="downloadReportPdf">导出 PDF</el-button>
          <el-button :icon="Document" @click="openVersions(selectedReport)">历史版本</el-button>
          <el-button :disabled="reportGenerating !== ''" @click="generateReport(selectedReport.report_type)">
            {{ reportGenerating === selectedReport.report_type ? '重新生成中…' : '重新生成' }}
          </el-button>
        </div>
        <el-skeleton v-if="detailLoading" :rows="6" animated style="padding:16px" class="surface" />
        <template v-else>
          <section class="surface panel">
            <div class="report-meta">
              <span>周期：{{ String(selectedReport.time_range_start || '').slice(0, 10) }} ~ {{ String(selectedReport.time_range_end || '').slice(0, 10) }}</span>
              <span>数据截止：{{ String(selectedReport.report_content?.header?.data_updated_at || '').slice(0, 19).replace('T', ' ') || '未标注' }}</span>
              <span>AI 分析：{{ aiSourceText(selectedReport.report_content) }}</span>
            </div>
            <p v-if="selectedReport.report_content?.summary" class="report-summary-text">{{ selectedReport.report_content.summary }}</p>
            <p v-if="selectedReport.report_content?.analysis" class="report-summary-text">{{ selectedReport.report_content.analysis }}</p>
            <ul v-if="selectedReport.report_content?.suggestions?.length" class="report-suggestions">
              <li v-for="(s, i) in selectedReport.report_content.suggestions" :key="i">{{ s.content }}<small v-if="s.department || s.owner">（{{ s.department || '待指定部门' }} · {{ s.owner || '待指定负责人' }}）</small></li>
            </ul>
          </section>

          <section v-if="selectedReport.report_content?.comparison" class="surface panel" style="margin-top:20px">
            <SectionTitle title="上一周期对比" desc="客户月报默认与上一个自然月比较；不可比时明确提示，不当作零。" />
            <p class="report-summary-text">{{ comparisonText(selectedReport.report_content.comparison) }}</p>
          </section>

          <section class="surface table-card" style="margin-top:20px">
            <SectionTitle title="核心指标" desc="「数据不可得」表示该指标缺上游数据，未用 0 或模拟值替代。" />
            <el-table :data="metricRows(selectedReport.report_content?.metrics)" size="small">
              <el-table-column prop="key" label="指标" min-width="240" />
              <el-table-column label="数值" width="220">
                <template #default="{ row }">
                  <span :class="{ muted: row.value === null || row.value === undefined }">{{ metricValueText(row.value) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <el-table v-if="selectedReport.report_type === 'customer_analysis'" :data="profileRows(selectedReport.report_content?.metrics)" size="small" style="margin-top:12px">
              <el-table-column prop="key" label="项目画像（四类）" min-width="240" />
              <el-table-column prop="value" label="分布" width="360" />
            </el-table>
            <p class="muted" style="padding:12px 4px 4px; line-height:1.8">{{ selectedReport.report_content?.data_notes }}</p>
          </section>

          <section class="surface panel" style="margin-top:20px">
            <SectionTitle
              title="明细下钻"
              desc="下钻为生成报告时固化的快照：源数据变化、AI 补分析都不会改变旧报告；个体信息按角色权限过滤。"
            />
            <div style="display:flex; gap:10px; margin-bottom:14px">
              <el-button v-if="selectedReport.report_type === 'customer_analysis'" :loading="drillLoading === 'customers'" @click="loadDrill('customers')">客户明细</el-button>
              <el-button v-if="selectedReport.report_type === 'psych_weekly'" :loading="drillLoading === 'psychCases'" @click="loadDrill('psychCases')">心理个案</el-button>
              <el-button v-if="selectedReport.report_type === 'complaint_weekly'" :loading="drillLoading === 'specialCases'" @click="loadDrill('specialCases')">投诉特别案例</el-button>
            </div>
            <el-alert v-if="drillNote" :title="drillNote" type="info" show-icon :closable="false" style="margin-bottom:12px" />

            <el-table v-if="drill.customers.length" :data="drill.customers" size="small">
              <el-table-column prop="name" label="客户" width="110" />
              <el-table-column prop="phone" label="手机号（脱敏）" width="130" />
              <el-table-column label="期末状态" width="110">
                <template #default="{ row }">{{ row.status ? row.status : '数据不可得' }}</template>
              </el-table-column>
              <el-table-column prop="source_channel" label="来源" width="150" />
              <el-table-column prop="owner_employee_id" label="负责人ID" width="100" />
              <el-table-column label="最新研判时间" width="160">
                <template #default="{ row }">{{ String(row.latest_assessment_at || '').slice(0, 19).replace('T', ' ') || '—' }}</template>
              </el-table-column>
              <el-table-column prop="sg_conclusion" label="新加坡画像" width="110" />
              <el-table-column prop="de_conclusion" label="德国画像" width="110" />
            </el-table>

            <el-table v-if="drill.psychCases.length" :data="drill.psychCases" size="small">
              <el-table-column prop="student_name" label="学生" width="100" />
              <el-table-column prop="student_contact" label="联系方式（脱敏）" width="140" />
              <el-table-column prop="risk_level" label="风险等级" width="90" />
              <el-table-column prop="emotion_tag" label="情绪标签" width="100" />
              <el-table-column prop="feedback_summary" label="反馈摘要" min-width="160" />
              <el-table-column prop="feedback_raw" label="反馈原文" min-width="180" />
              <el-table-column label="周期内历史" width="220">
                <template #default="{ row }">{{ historyText(row.history) }}</template>
              </el-table-column>
              <el-table-column prop="responsible_employee_id" label="负责员工ID" width="110" />
            </el-table>

            <el-table v-if="drill.specialCases.length" :data="drill.specialCases" size="small">
              <el-table-column prop="ticket_id" label="工单号" width="90" />
              <el-table-column prop="student_name" label="学生" width="100" />
              <el-table-column prop="student_contact" label="联系方式（脱敏）" width="140" />
              <el-table-column label="类型来源" width="110">
                <template #default="{ row }">{{ row.category_source === 'student' ? '学生所选' : row.category_source === 'ai' ? 'AI 分类' : '未分类' }}</template>
              </el-table-column>
              <el-table-column prop="satisfaction" label="满意度" width="90" />
              <el-table-column prop="content" label="工单内容" min-width="160" />
              <el-table-column prop="detail" label="补充说明" min-width="150" />
              <el-table-column prop="ai_summary" label="AI 归纳理由" min-width="180" />
              <el-table-column prop="progress" label="处理过程" min-width="130" />
            </el-table>

            <el-empty v-if="selectedReport.report_type === 'customer_analysis' && drill.customers.length === 0 && drillLoading !== 'customers'"
                      description="点击「客户明细」加载下钻快照" :image-size="60" />
            <el-empty v-else-if="selectedReport.report_type === 'psych_weekly' && drill.psychCases.length === 0 && drillLoading !== 'psychCases'"
                      description="点击「心理个案」加载下钻快照（仅本人负责或管理层可见）" :image-size="60" />
            <el-empty v-else-if="selectedReport.report_type === 'complaint_weekly' && drill.specialCases.length === 0 && drillLoading !== 'specialCases'"
                      description="点击「投诉特别案例」加载下钻快照（仅 MANAGER/ADMIN）" :image-size="60" />
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
        <el-select v-model="customerOwnerFilter" style="width:150px"><el-option label="全部员工" value="all" /><el-option v-for="emp in employeeRows" :key="emp.id" :label="emp.real_name" :value="emp.id" /></el-select>
        <el-select v-model="customerStatusFilter" style="width:140px"><el-option label="全部状态" value="all" /><el-option v-for="option in customerStatusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select>
        <el-select v-model="reassignFromId" placeholder="原归属员工" style="width:150px"><el-option v-for="emp in employeeRows" :key="emp.id" :label="emp.real_name" :value="emp.id" /></el-select>
        <el-select v-model="reassignToId" placeholder="目标员工" style="width:150px"><el-option v-for="emp in employeeRows" :key="emp.id" :label="emp.real_name" :value="emp.id" /></el-select>
        <el-button @click="batchReassign">批量再分配</el-button>
      </div>
      <section class="surface table-card">
        <el-table :data="filteredCustomers" @row-click="(row:any) => activeCustomer = row" @selection-change="onCustomerSelection">
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
              <el-button text @click.stop="openReassign(row)">改归属</el-button>
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
          <div class="drawer-actions"><el-button type="primary" @click="addFollowUp">添加跟进</el-button><el-button @click="openReassign(activeCustomer)">变更归属</el-button></div>
        </template>
      </el-drawer>
      <el-dialog v-model="reassignDialog" title="变更客户归属" width="min(420px, 92vw)">
        <p class="muted">客户：{{ reassignCustomer?.name || '—' }} · 当前跟进人：{{ employeeName(reassignCustomer?.owner_employee_id) }}</p>
        <el-select v-model="reassignDialogTargetId" placeholder="请选择目标员工" style="width:100%"><el-option v-for="emp in employeeRows" :key="emp.id" :label="emp.real_name" :value="emp.id" /></el-select>
        <template #footer>
          <el-button @click="reassignDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmReassign">确认变更</el-button>
        </template>
      </el-dialog>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'approvals'">
      <SectionTitle title="审批任务" desc="统一处理员工转化申请、请假、日报补报和投诉处理，支持批量通过。">
        <el-button type="primary" @click="confirmWrite('确认批量通过所选申请吗？', batchApprove)">批量通过</el-button>
      </SectionTitle>
      <div class="approval-filters"><el-radio-group v-model="approvalFilter"><el-radio-button value="全部">全部</el-radio-button><el-radio-button value="转化申请">转化申请</el-radio-button><el-radio-button value="请假">请假</el-radio-button><el-radio-button value="员工流程">员工流程</el-radio-button></el-radio-group></div>
      <div class="approval-grid">
        <article v-for="item in filteredApprovalItems" :key="item.id" class="surface approval-card">
          <div class="approval-top"><el-checkbox :model-value="selectedApprovals.includes(item.id)" @change="(checked: any) => toggleApproval(item.id, !!checked)" /><el-tag>{{ approvalBizLabel[item.biz_type] || item.biz_type || '审批' }}</el-tag><el-tag :type="item.status === 'approved' ? 'success' : item.status === 'rejected' ? 'info' : 'warning'">{{ approvalStatusLabel[item.status] || item.status }}</el-tag></div>
          <h3>{{ item.title || (item.biz_type + ' #' + item.id) }}</h3>
          <p>提交时间：{{ (item.created_at || item.create_time || '—').toString().slice(0, 10) }} · 一次审批</p>
          <div><el-button type="primary" @click="confirmWrite('确认通过该申请吗？', () => approveItem(item))">通过</el-button><el-button @click="confirmWrite('确认驳回该申请吗？申请人可修改后重新提交。', () => rejectItem(item))">驳回</el-button><el-button text>查看详情</el-button></div>
        </article>
        <el-empty v-if="!filteredApprovalItems.length" description="暂无待审批的申请" />
      </div>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'employees'">
      <SectionTitle title="员工账号与权限" desc="一期不设置独立人事角色，员工账号和状态在此统一管理。"><el-button type="primary" :icon="Plus" @click="openCreateUser">创建员工账号</el-button></SectionTitle>
      <section class="surface table-card"><el-table :data="employeeRows"><el-table-column prop="real_name" label="员工" /><el-table-column prop="department" label="部门" /><el-table-column label="角色"><template #default="{ row }">{{ row.employee_role || (row.user_type === 'MANAGER' ? '管理层' : '普通员工') }}</template></el-table-column><el-table-column label="本月客户" width="110"><template #default>—</template></el-table-column><el-table-column prop="status" label="状态" /><el-table-column label="操作"><template #default="{ row }"><el-button text type="primary" @click="openPermissionConfig(row.id)">权限</el-button></template></el-table-column></el-table><el-empty v-if="!employeeRows.length" description="暂无员工账号" /></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'permissions'">
      <section class="surface panel permission-panel"><SectionTitle title="权限项配置" desc="一期使用 user_type 粗判和数据隔离，权限项配置界面为管理层工具。" /><el-form label-position="top"><el-form-item label="选择用户"><el-select v-model="permissionUserId" filterable placeholder="请选择用户" style="width:100%"><el-option v-for="emp in employeeRows" :key="emp.id" :label="(emp.real_name || '—') + ' · ' + (emp.department || emp.employee_role || (emp.user_type === 'MANAGER' ? '管理层' : '普通员工'))" :value="emp.id" /></el-select></el-form-item><el-empty v-if="!employeeRows.length" description="暂无员工账号" /><el-checkbox-group v-model="permissionDraft"><el-checkbox v-for="perm in permissionOptions" :key="perm.key" :value="perm.key">{{ perm.label }}</el-checkbox></el-checkbox-group><el-button type="primary" style="margin-top:22px" @click="confirmWrite('确认保存权限配置吗？', savePermissionConfig)">保存权限配置</el-button></el-form></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'logs'">
      <SectionTitle title="消息中心与操作日志" desc="展示审批结果、预警通知、系统公告和关键操作记录。" />
      <div class="two-column"><section class="surface panel"><SectionTitle title="消息中心" /><el-button v-if="notificationRows.length" text type="primary" @click="markAllNotifications">全部已读</el-button><div v-for="item in notificationRows" :key="item.id" class="task-row" style="cursor: pointer" @click="markNotification(item)"><b>{{ item.is_read ? '✓' : '!' }}</b><div><strong>{{ item.title || item.content || '站内通知' }}</strong><small>{{ item.type || '系统' }} · {{ String(item.created_at || '').slice(11, 16) || '刚刚' }} · {{ item.is_read ? '已读' : '未读' }}</small></div></div><el-empty v-if="!notificationRows.length" description="暂无消息" /></section><section class="surface panel"><SectionTitle title="关键操作日志" /><div v-for="log in operationLogRows" :key="log.id" class="task-row"><b>•</b><div><strong>{{ (logModuleLabel[log.module] || log.module) + ' · ' + (logActionLabel[log.action] || log.action) }}</strong><small>{{ operatorName(log.user_id) }} · {{ String(log.created_at || '').slice(0, 16).replace('T', ' ') || '—' }}</small></div></div><el-empty v-if="!operationLogRows.length" description="暂无操作日志" /></section></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'courses'">
      <SectionTitle title="课程与项目" desc="登录后可提交报名咨询。" /><div class="service-grid"><article v-for="item in publicProjects.slice(0,4)" :key="item.id" class="surface service-card"><div class="service-icon">{{ item.category.slice(0,2) }}</div><h3>{{ item.title }}</h3><p>{{ item.summary }}</p><el-button type="primary" round @click="router.push('/projects/' + item.id)">了解并咨询</el-button></article></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'events'">
      <SectionTitle title="活动报名" desc="已登录，可直接报名近期活动。" /><div class="event-list"><div v-for="item in publicEvents.slice(0,3)" :key="item.id" class="surface ticket-row"><div><b>{{ item.title }}</b><small>{{ item.date }} · {{ item.format }}</small></div><el-button type="primary" round @click="applyEvent(item)">报名</el-button></div></div>
    </template>

    <template v-else-if="role === 'PROSPECT' && section === 'consult'">
      <SectionTitle title="我的咨询" desc="记录与顾问沟通和报名进度。" /><section class="surface panel"><div v-if="consultRows.length"><div v-for="(item, index) in consultRows" :key="index" class="ticket-row"><div><b>{{ item.project }}</b><small>{{ item.time }} · {{ item.name }} {{ item.phone }}</small><small>{{ item.note }}</small></div><el-tag type="success">已提交</el-tag></div></div><el-empty v-else description="暂无进行中的咨询"><el-button type="primary" @click="router.push('/projects')">去看看项目</el-button></el-empty></section>
    </template>

    <template v-else-if="role === 'MANAGER' && section === 'org'">
      <SectionTitle title="组织架构查询" desc="查看部门职能、团队层级和同事联系方式；联系方式默认脱敏。" />
      <div class="two-column">
        <section class="surface panel"><el-input :prefix-icon="Search" placeholder="搜索部门或姓名" /><el-tree :data="orgTree" :props="orgTreeProps" default-expand-all /></section>
        <section class="surface panel"><SectionTitle title="组织能力" /><div class="life-grid"><article v-for="item in ['部门职能查询','同事联系方式','团队成员筛选','组织变更记录']" :key="item" class="surface life-card"><h3>{{ item }}</h3><p>按部门、经理和员工维度查看组织数据。</p></article></div></section>
      </div>
    </template>

    <template v-else>
      <section class="surface profile-card"><SectionTitle title="模块详情" /><p class="muted">该页面已按当前角色和模块建立完整结构。后续接入对应接口时，将替换数据来源和操作处理。</p><el-button type="primary" @click="router.push('/app/' + role.toLowerCase() + '/home')">返回工作台</el-button></section>
    </template>
  </div>
    <el-dialog v-model="createUserDialog" title="创建员工账号" width="min(520px, 94vw)"><el-form label-position="top"><el-form-item label="真实姓名"><el-input v-model="createUserForm.real_name" placeholder="请输入真实姓名" /></el-form-item><el-form-item label="登录用户名"><el-input v-model="createUserForm.username" placeholder="3-50 位，需唯一" /></el-form-item><el-form-item label="手机号"><el-input v-model="createUserForm.phone" placeholder="选填，需唯一" /></el-form-item><el-form-item label="初始密码"><el-input v-model="createUserForm.password" type="password" show-password placeholder="至少 6 位" /></el-form-item><el-form-item label="账号类型"><el-radio-group v-model="createUserForm.user_type"><el-radio value="EMPLOYEE">普通员工</el-radio><el-radio value="MANAGER">管理层</el-radio></el-radio-group></el-form-item><el-form-item label="部门"><el-input v-model="createUserForm.department" placeholder="选填，如 咨询部" /></el-form-item><el-form-item label="岗位角色"><el-input v-model="createUserForm.employee_role" placeholder="选填，如 留学顾问" /></el-form-item></el-form><template #footer><el-button @click="createUserDialog = false">取消</el-button><el-button type="primary" @click="submitCreateUser">确认创建</el-button></template></el-dialog>
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
    <el-dialog v-model="versionDialog" title="历史版本（同类型同周期）" width="min(720px, 94vw)">
      <el-skeleton v-if="versionLoading" :rows="4" animated />
      <el-empty v-else-if="versionRows.length === 0" description="暂无历史版本" :image-size="60" />
      <el-table v-else :data="versionRows" size="small">
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="周期" width="200">
          <template #default="{ row }">{{ String(row.time_range_start || '').slice(0, 10) }} ~ {{ String(row.time_range_end || '').slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据来源" width="110">
          <template #default="{ row }">{{ row.data_source_status === 'production' ? '正式数据' : '演示数据' }}</template>
        </el-table-column>
        <el-table-column label="生成时间" width="170">
          <template #default="{ row }">{{ String(row.created_at || '').slice(0, 19).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }"><el-button text type="primary" @click="openVersion(row)">查看</el-button></template>
        </el-table-column>
      </el-table>
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

.student-progress-panel { min-width: 0; overflow: hidden; }
.student-progress-panel .student-progress-steps { width: 100%; padding: 2px 0 6px; }
.student-progress-panel .student-progress-steps .el-step { min-height: 58px; }
.student-progress-panel .student-progress-steps .el-step__head { width: 24px; height: 24px; line-height: 24px; }
.student-progress-panel .student-progress-steps .el-step__icon { width: 24px; height: 24px; line-height: 23px; font-size: 12px; }
.student-progress-panel .student-progress-steps .el-step__line { left: 11px; top: 24px; bottom: 0; height: auto; background: var(--line); }
.student-progress-panel .student-progress-steps .el-step__main { min-height: 58px; padding-bottom: 6px; }
.student-progress-panel .student-progress-steps .el-step__title { margin-top: 1px; font-size: 14px; line-height: 22px; color: var(--ink-deep); }
.student-progress-panel .student-progress-steps .el-step__description { margin-top: 0; padding-right: 0; font-size: 12px; line-height: 18px; color: var(--muted); }
@media (max-width: 760px) {
  .student-progress-panel .student-progress-steps .el-step,
  .student-progress-panel .student-progress-steps .el-step__main { min-height: 54px; }
}

</style>
