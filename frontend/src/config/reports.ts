/**
 * M5 智能报告：report_type 枚举与前端 tab 编码的唯一映射（M5-05.5）。
 * 后端枚举以 backend/app/schemas/report.py ReportType 为准，此处不得增删改名。
 */
export const REPORT_TYPES = [
  { type: 'customer_analysis', code: 'CA', name: '客户经营分析报告', period: '周报 / 月报' },
  { type: 'daily_report_summary', code: 'DS', name: '员工日报汇总', period: '日报' },
  { type: 'weekly_report_summary', code: 'WS', name: '员工周报汇总', period: '周报' },
  { type: 'psych_weekly', code: 'PW', name: '学生心理健康周报', period: '周报' },
  { type: 'complaint_weekly', code: 'CW', name: '投诉处理周报', period: '周报' },
] as const

export type ReportTypeItem = (typeof REPORT_TYPES)[number]

export function typeName(reportType: string): string {
  return REPORT_TYPES.find(t => t.type === reportType)?.name || reportType
}

export function typeCode(reportType: string): string {
  return REPORT_TYPES.find(t => t.type === reportType)?.code || reportType
}
