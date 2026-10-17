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

export const platformApi = {
  projects: () => fallback(() => request.get('/cs/courses'), projects),
  events: () => fallback(() => request.get('/cs/events'), events),
  faqs: () => fallback(() => request.get('/cs/faq'), faqs),
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

