import request from '../utils/request'
import { customers, events, faqs, notifications, policies, projects } from '../data/mock'

type AnyRecord = Record<string, any>

async function toData<T>(promise: Promise<any>): Promise<T> {
  const body = await promise
  return (body?.data ?? body) as T
}

async function fallback<T>(task: () => Promise<any>, data: T): Promise<T> {
  try {
    return await toData<T>(task())
  } catch (error) {
    // M5-05.7：静默回落必须显式提示——控制台可追溯，避免 mock 数据被误当真实接口数据
    console.warn('[platformApi] 接口不可用，回落到本地演示数据：', error)
    return data
  }
}

function query(params: AnyRecord = {}) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
}

function eventDateLabel(value: any): string {
  const d = new Date(value)
  if (!value || isNaN(d.getTime())) return '—'
  return d.getMonth() + 1 + '月' + d.getDate() + '日'
}

export const platformApi = {
  // v6.10.0：课程列表切真实 GET /cs/courses（原指向恒 404 降级 mock）；
  // 映射页面展示形状（tag/status、fee/tuition_fee、highlights 表无对应列置空），降级 mock 不加 demo 标记（课程无报名态）
  projects: async (): Promise<Array<AnyRecord>> => {
    try {
      const data: any = await toData(request.get('/cs/courses', { params: { page_size: 100 } }))
      if (data?.items?.length) {
        return data.items.map((i: AnyRecord) => ({
          id: i.id,
          title: i.project_name,
          category: i.category || '国际留学',
          tag: i.status || '热招',
          summary: i.description || '—',
          audience: i.target_audience || '—',
          duration: i.duration || '—',
          fee: i.tuition_fee != null && i.tuition_fee !== '' ? '¥' + i.tuition_fee : '费用面议',
          highlights: [] as string[],
        }))
      }
    } catch (error) {
      // M5-05.7：静默回落必须显式提示——控制台可追溯，避免 mock 数据被误当真实接口数据
      console.warn('[platformApi] 接口不可用，回落到本地演示数据：', error)
    }
    return projects
  },
  // v6.9.8 ②-A：活动列表切真实 GET /events（原指向未实装的 /cs/events 恒 404 降级 mock）；
  // 映射页面展示形状并保留真实 id/status（报名与禁用判断依赖）；降级 mock 追加 demo 标记供页面禁用报名
  events: async (): Promise<Array<AnyRecord>> => {
    try {
      const data: any = await toData(request.get('/events', { params: { page_size: 100 } }))
      if (data?.items?.length) {
        return data.items.map((i: AnyRecord) => ({
          id: i.id,
          date: eventDateLabel(i.start_time),
          title: i.event_name,
          format: [i.event_type, i.location].filter(Boolean).join(' · ') || '—',
          speaker: '—', // event_lecture 表无主讲人列（②-A 既定决策：显示"—"，不动表结构）
          joined: i.current_participants ?? 0,
          capacity: i.max_participants ?? 0,
          status: i.status,
        }))
      }
    } catch (error) {
      // M5-05.7：静默回落必须显式提示——控制台可追溯，避免 mock 数据被误当真实接口数据
      console.warn('[platformApi] 接口不可用，回落到本地演示数据：', error)
    }
    return events.map((e: AnyRecord) => ({ ...e, demo: true }))
  },
  eventRegister: (id: number) => toData(request.post('/events/' + id + '/register')),
  faqs: async (): Promise<Array<{ q: string; a: string }>> => {
    try {
      const data: any = await toData(request.get('/cs/faq', { params: { page_size: 100 } }))
      if (data?.items?.length) return data.items.map((i: AnyRecord) => ({ q: i.question, a: i.answer }))
    } catch { /* 后端未就绪时降级 mock */ }
    return faqs
  },
  csChat: (data: AnyRecord) => toData(request.post('/ai/customer-service/chat', data)),
  policies: () => Promise.resolve(policies),
  notifications: (params: AnyRecord = {}) => fallback(() => request.get('/notifications', { params: query(params) }), notifications),
  notificationsUnread: () => toData(request.get('/notifications/unread-count')),
  markNotificationRead: (id: number) => toData(request.put('/notifications/' + id + '/read')),
  markAllNotificationsRead: () => toData(request.put('/notifications/read-all')),
  customers: (params: AnyRecord = {}) => fallback(() => request.get('/customers', { params: query(params) }), { items: customers, total: customers.length, page: 1, page_size: 20 }),
  customer: (id: number) => toData(request.get('/customers/' + id)),
  createCustomer: (data: AnyRecord) => toData(request.post('/customers', data)),
  updateCustomer: (id: number, data: AnyRecord) => toData(request.put('/customers/' + id, data)),
  employeeCustomers: (params: AnyRecord = {}) => fallback(() => request.get('/employee/customers', { params: query(params) }), { items: customers, total: customers.length, page: 1, page_size: 20 }),
  employeeReminders: () => fallback(() => request.get('/employee/reminders'), { todos_pending: 4, follow_ups_due: 2, admin_services_pending: 1, psych_alerts_pending: 1, approvals_pending: 3 }),
  employeeProfile: () => fallback(() => request.get('/employee/profile'), { real_name: '陈顾问', department: '新加坡事业部', phone: '138****2266', contact_info: '企业微信：粤教陈顾问' }),
  employee: {
    submitReport: (data: AnyRecord) => toData(request.post('/employee/reports', data)),
    updateDraft: (id: number, data: AnyRecord) => toData(request.put('/employee/reports/' + id, data)),
    lateApply: (id: number, data: AnyRecord) => toData(request.post('/employee/reports/' + id + '/late-apply', data)),
    lateReview: (data: AnyRecord) => toData(request.post('/employee/reports/late-review', data)),
    listReports: (params: AnyRecord = {}) => toData(request.get('/employee/reports', { params: query(params) })),
    reportsSummary: (params: AnyRecord = {}) => toData(request.get('/employee/reports/summary', { params: query(params) })),
    createTodo: (data: AnyRecord) => toData(request.post('/employee/todos', data)),
    listTodos: (params: AnyRecord = {}) => toData(request.get('/employee/todos', { params: query(params) })),
    updateTodo: (id: number, data: AnyRecord) => toData(request.put('/employee/todos/' + id, data)),
    org: (params: AnyRecord = {}) => toData(request.get('/employee/org', { params: query(params) })),
    orgMembers: (params: AnyRecord = {}) => toData(request.get('/employee/org/members', { params: query(params) })),
    revealPhone: (userId: number) => toData(request.post('/employee/org/members/' + userId + '/reveal-phone')),
    listScores: (params: AnyRecord = {}) => toData(request.get('/employee/scores', { params: query(params) })),
    createScore: (data: AnyRecord) => toData(request.post('/employee/scores', data)),
    createConvertApply: (data: AnyRecord) => toData(request.post('/employee/convert-applies', data)),
    listAdminServices: (params: AnyRecord = {}) => toData(request.get('/employee/admin-services', { params: query(params) })),
    reviewAdminService: (id: number, data: AnyRecord) => toData(request.post('/employee/admin-services/' + id + '/review', data)),
    oralReport: (data: AnyRecord) => toData(request.post('/employee/reports/oral', data)),
    createCrmLead: (data: AnyRecord) => toData(request.post('/employee/crm/leads', data)),
    createFollowUp: (data: AnyRecord) => toData(request.post('/employee/crm/follow-ups', data)),
    listFollowUps: (params: AnyRecord = {}) => toData(request.get('/employee/crm/follow-ups', { params: query(params) })),
    parseCommand: (data: AnyRecord) => toData(request.post('/employee/commands/parse', data)),
    executeCommand: (data: AnyRecord) => toData(request.post('/employee/commands/execute', data)),
    updateCustomerStatus: (id: number, data: AnyRecord) => toData(request.patch('/employee/customers/' + id + '/status', data)),
    listTickets: (params: AnyRecord = {}) => toData(request.get('/employee/tickets', { params: query(params) })),
    handleTicket: (id: number, data: AnyRecord) => toData(request.post('/employee/tickets/' + id + '/handle', data)),
    handlePsychAlert: (id: number, data: AnyRecord) => toData(request.post('/employee/psych-alerts/' + id + '/handle', data)),
    createAnnotation: (id: number, data: AnyRecord) => toData(request.post('/employee/reports/' + id + '/annotations', data)),
    listAnnotations: (id: number) => toData(request.get('/employee/reports/' + id + '/annotations')),
    reassignCustomers: (data: AnyRecord) => toData(request.post('/employee/customers/reassign', data)),
    updateProfile: (data: AnyRecord) => toData(request.put('/employee/profile', data)),
    changePassword: (data: AnyRecord) => toData(request.put('/employee/profile/password', data)),
    profileStats: () => toData(request.get('/employee/profile/stats')),
    exportCustomers: () => request.get('/employee/export/customers', { responseType: 'blob' }),
    exportDailyReports: (params: AnyRecord = {}) => request.get('/employee/export/daily-reports', { params: query(params), responseType: 'blob' }),
    exportTickets: (params: AnyRecord = {}) => request.get('/employee/export/tickets', { params: query(params), responseType: 'blob' }),
    exportFollowUps: (params: AnyRecord = {}) => request.get('/employee/export/follow-ups', { params: query(params), responseType: 'blob' }),
    agentChat: (data: AnyRecord) => toData(request.post('/employee/agent/chat', data)),
    guideOnboarding: () => toData(request.get('/employee/guide/onboarding')),
    guideAsk: (data: AnyRecord) => toData(request.post('/employee/guide/ask', data)),
    dashboard: () => toData(request.get('/employee/dashboard')),
    approvalsCenter: (params: AnyRecord = {}) => toData(request.get('/employee/approvals-center', { params: query(params) })),
    listUsers: (params: AnyRecord = {}) => toData(request.get('/employee/users', { params: query(params) })),
    createUser: (data: AnyRecord) => toData(request.post('/employee/users', data)),
    updateUserStatus: (id: number, data: AnyRecord) => toData(request.patch('/employee/users/' + id + '/status', data)),
    updateUserPermissions: (id: number, data: AnyRecord) => toData(request.put('/employee/users/' + id + '/permissions', data)),
  },
  approvals: {
    create: (data: AnyRecord) => toData(request.post('/approvals', data)),
    approve: (id: number, data: AnyRecord = {}) => toData(request.post('/approvals/' + id + '/approve', data)),
    reject: (id: number, data: AnyRecord = {}) => toData(request.post('/approvals/' + id + '/reject', data)),
    batchApprove: (data: AnyRecord) => toData(request.post('/approvals/batch-approve', data)),
    pending: (params: AnyRecord = {}) => toData(request.get('/approvals/pending', { params: query(params) })),
    my: () => toData(request.get('/approvals/my')),
    get: (id: number) => toData(request.get('/approvals/' + id)),
  },
  // M5 智能报告（M5-05.6/05.7）：报告组不做静默 mock 回落——失败直接抛出由页面四态呈现
  reports: {
    list: (params: AnyRecord = {}) => toData(request.get('/reports', { params: query(params) })),
    generate: (data: AnyRecord) => toData(request.post('/reports/generate', data)),
    get: (id: number) => toData(request.get('/reports/' + id)),
    // v6.11.0 §2.1：同类型同周期的历史版本
    versions: (reportType: string, periodStart: string, periodEnd: string) =>
      toData(request.get('/reports/versions', {
        params: { report_type: reportType, period_start: periodStart, period_end: periodEnd },
      })),
    customers: (id: number) => toData(request.get('/reports/' + id + '/customers')),
    psychCases: (id: number) => toData(request.get('/reports/' + id + '/psych_cases')),
    specialCases: (id: number) => toData(request.get('/reports/' + id + '/special_cases')),
    download: (id: number) => request.get('/reports/' + id + '/download', { responseType: 'blob' }),
  },
  student: {
    submitAdminService: (data: AnyRecord) => toData(request.post('/student/admin-services', data)),
    listAdminServices: (params: AnyRecord = {}) => toData(request.get('/student/admin-services', { params: query(params) })),
    psychChat: (data: AnyRecord) => toData(request.post('/student/psych/chat', data)),
    psychProfile: () => toData(request.get('/student/psych/profile')),
    submitTicket: (data: AnyRecord) => toData(request.post('/student/tickets', data)),
    listTickets: (params: AnyRecord = {}) => toData(request.get('/student/tickets', { params: query(params) })),
    academic: () => toData(request.get('/student/academic')),
    progress: () => toData(request.get('/student/progress')),
    updateProgress: (studentId: number, data: AnyRecord) => toData(request.put('/employee/students/' + studentId + '/progress', data)),
    lifeFaq: () => toData(request.get('/student/life/faq')),
    moreServices: () => toData(request.get('/student/services')),
    agentChat: (data: AnyRecord) => toData(request.post('/student/agent/chat', data)),
    reminders: () => toData(request.get('/student/reminders')),
  },
  users: {
    updateMe: (data: AnyRecord) => toData(request.put('/users/me', data)),
  },
  files: {
    upload: (module: string, file: File) => {
      const form = new FormData()
      form.append('module', module)
      form.append('file', file)
      return toData(request.post('/files/upload', form))
    },
    download: (objectName: string) => request.get('/files/download', { params: { object_name: objectName }, responseType: 'blob' }),
    presigned: (objectName: string) => toData(request.get('/files/presigned', { params: { object_name: objectName } })),
  },
}

