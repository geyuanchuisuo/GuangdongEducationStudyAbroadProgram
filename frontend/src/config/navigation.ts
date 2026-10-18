export type Role = 'PROSPECT' | 'STUDENT' | 'EMPLOYEE' | 'MANAGER'

export type NavItem = {
  key: string
  label: string
  icon: string
  section: string
}

export const navigation: Record<Role, NavItem[]> = {
  PROSPECT: [
    { key: 'home', label: '我的首页', icon: 'House', section: 'home' },
    { key: 'courses', label: '课程与项目', icon: 'Collection', section: 'courses' },
    { key: 'events', label: '活动报名', icon: 'Calendar', section: 'events' },
    { key: 'consult', label: '我的咨询', icon: 'ChatLineRound', section: 'consult' },
    { key: 'profile', label: '个人信息', icon: 'User', section: 'profile' },
  ],
  STUDENT: [
    { key: 'home', label: '学生首页', icon: 'House', section: 'home' },
    { key: 'admin', label: '行政服务', icon: 'Document', section: 'admin' },
    { key: 'psych', label: '心理关怀', icon: 'Star', section: 'psych' },
    { key: 'feedback', label: '售后反馈', icon: 'Service', section: 'feedback' },
    { key: 'academic', label: '学业考务', icon: 'Calendar', section: 'academic' },
    { key: 'progress', label: '进度追踪', icon: 'TrendCharts', section: 'progress' },
    { key: 'life', label: '生活支持', icon: 'Location', section: 'life' },
    { key: 'more', label: '更多服务', icon: 'MagicStick', section: 'more' },
    { key: 'profile', label: '个人信息', icon: 'User', section: 'profile' },
  ],
  EMPLOYEE: [
    { key: 'home', label: '工作台', icon: 'House', section: 'home' },
    { key: 'customers', label: '客户经营', icon: 'UserFilled', section: 'customers' },
    { key: 'assessment', label: '客户研判', icon: 'Search', section: 'assessment-tool' },
    { key: 'convert', label: '学生业务综管', icon: 'Finished', section: 'convert' },
    { key: 'reports', label: '日报管理', icon: 'EditPen', section: 'reports' },
    { key: 'scores', label: '成绩录入', icon: 'DataLine', section: 'scores' },
    { key: 'org', label: '组织与指引', icon: 'OfficeBuilding', section: 'org' },
    { key: 'todos', label: '待办与消息', icon: 'Bell', section: 'todos' },
    { key: 'profile', label: '个人信息', icon: 'User', section: 'profile' },
  ],
  MANAGER: [
    { key: 'home', label: '经营看板', icon: 'DataAnalysis', section: 'home' },
    { key: 'reports', label: '智能汇总', icon: 'DataAnalysis', section: 'reports' },
    { key: 'org', label: '组织架构', icon: 'OfficeBuilding', section: 'org' },
    { key: 'approvals', label: '流程审批', icon: 'Finished', section: 'approvals' },
    { key: 'customers', label: '全部客户', icon: 'UserFilled', section: 'customers' },
    { key: 'assessment', label: '客户研判', icon: 'Search', section: 'assessment-tool' },
    { key: 'employees', label: '员工管理', icon: 'User', section: 'employees' },
    { key: 'permissions', label: '权限配置', icon: 'Lock', section: 'permissions' },
    { key: 'logs', label: '消息与日志', icon: 'Bell', section: 'logs' },
    { key: 'profile', label: '个人信息', icon: 'User', section: 'profile' },
  ],
}

