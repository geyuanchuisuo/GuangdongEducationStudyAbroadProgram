import request from '../utils/request'
import { customers, events, faqs, notifications, policies, projects, reports } from '../data/mock'

async function fallback<T>(task: () => Promise<any>, data: T): Promise<T> {
  try {
    const res: any = await task()
    return res.data ?? res ?? data
  } catch {
    return data
  }
}

export const platformApi = {
  projects: () => fallback(() => request.get('/cs/courses'), projects),
  events: () => fallback(() => request.get('/cs/events'), events),
  faqs: () => fallback(() => request.get('/cs/faq'), faqs),
  policies: () => Promise.resolve(policies),
  notifications: () => fallback(() => request.get('/notifications'), notifications),
  customers: () => fallback(() => request.get('/employee/customers'), customers),
  reports: () => fallback(() => request.get('/reports'), reports),
  reminders: () => fallback(() => request.get('/employee/reminders'), {
    todos_pending: 4,
    follow_ups_due: 2,
    admin_services_pending: 1,
    psych_alerts_pending: 1,
    approvals_pending: 3,
  }),
  employeeProfile: () => fallback(() => request.get('/employee/profile'), {
    real_name: '陈顾问',
    department: '新加坡事业部',
    phone: '138****2266',
    contact_info: '企业微信：粤教陈顾问',
  }),
}

