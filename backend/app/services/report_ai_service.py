"""M5 智能报告模块 — AI 分析（阶段 5）

AI 只负责摘要 / 趋势 / 分析 / 建议的文字归纳，数字一律由程序计算后作为输入传入，
禁止 AI 自行计算或编造。一期未配置报告 Agent，使用确定性模拟输出（明确标注"模拟"）；
未来接入真实 Agent 后只替换 analyze 的实现，输出结构与降级逻辑不变。
调用失败时返回 None，由调用方保留确定性统计并标记 AI 不可用。
"""
import logging

from app.services.model_ai_service import model_ai_service

logger = logging.getLogger(__name__)


def _suggestion(content: str) -> dict:
    """一期建议只展示、不自动创建待办；负责部门/负责人由人工补充。"""
    return {"content": content, "department": None, "owner": None, "status": "待处理"}


def _mock_analysis(report_type: str, metrics: dict) -> dict:
    """确定性模拟 AI 输出：仅复述程序计算出的指标，不自行计算。"""
    if report_type == "customer_analysis":
        ov = metrics["status_overview"]
        sg = metrics["profiles"]["sg_conclusion"]
        de = metrics["profiles"]["de_conclusion"]
        return {
            "summary": (
                f"（模拟）本期新增客户 {metrics['new_this_period']} 名，"
                f"期末意向 {ov['intent']} 名、成交 {ov['converted']} 名、流失 {ov['lost']} 名。"
            ),
            "trend": None,  # 一期无上周数据，对比在阶段 6 接入历史后补齐
            "analysis": (
                f"（模拟）画像方面，新加坡：符合 {sg['符合']}、不符合 {sg['不符合']}、信息不足 {sg['信息不足']}；"
                f"德国：符合 {de['符合']}、不符合 {de['不符合']}、信息不足 {de['信息不足']}。"
            ),
            "suggestions": [_suggestion("（模拟）关注信息不足客户的研判补全")],
        }

    if report_type in ("daily_report_summary", "weekly_report_summary"):
        total = metrics["week_total"]
        depts = metrics["departments"]
        missing_depts = "、".join(
            d for d, v in depts.items() if v["missing"] > 0
        ) or "无"
        return {
            "summary": (
                f"（模拟）全周应提交 {total['should_submit']} 人次、已提交 {total['submitted']} 人次、"
                f"未提交 {total['missing']} 人次。"
            ),
            "trend": None,
            "analysis": f"（模拟）存在未提交的部门：{missing_depts}。",
            "suggestions": [_suggestion("（模拟）跟进未提交日报的员工")],
        }

    if report_type == "psych_weekly":
        risk = metrics["risk"]
        return {
            "summary": (
                f"（模拟）本期覆盖学生 {metrics['covered_students']} 名，"
                f"其中高风险 {risk['高']} 名、中风险 {risk['中']} 名、低风险 {risk['低']} 名。"
            ),
            "trend": None,
            "analysis": "（模拟）高风险个案需按学生模块流程即时关注，不等待周报。",
            "suggestions": [_suggestion("（模拟）对高风险个案保持跟进")],
        }

    if report_type == "complaint_weekly":
        sat = metrics["satisfaction"]
        avg = metrics["avg_first_response_seconds"]
        avg_h = round(avg / 3600, 1) if avg is not None else None
        return {
            "summary": (
                f"（模拟）本期新增投诉 {metrics['new_count']} 件，"
                f"期末未解决 {metrics['open_count']} 件、超过七天未解决 {metrics['over7_unresolved']} 件。"
            ),
            "trend": None,
            "analysis": (
                f"（模拟）平均首次响应时长 {avg_h} 小时，"
                f"满意度：满意 {sat['满意']}、不满意 {sat['不满意']}、未评价 {sat['未评价']}。"
            ),
            "suggestions": [_suggestion("（模拟）优先处理长期未解决与未响应投诉")],
        }

    raise ValueError(f"未知报告类型: {report_type}")


_KEYS = ("summary", "trend", "analysis", "suggestions")


def _validate(analysis: dict) -> dict | None:
    """AI 输出结构校验：缺失/类型不符则视为失败。"""
    if not isinstance(analysis, dict):
        return None
    if not all(k in analysis for k in _KEYS):
        return None
    if not isinstance(analysis["summary"], str) or not isinstance(analysis["analysis"], str):
        return None
    if not isinstance(analysis["suggestions"], list):
        return None
    return analysis


class ReportAIService:
    """报告 AI 分析入口。一期未配置报告 Agent，使用模拟输出。"""

    async def analyze(self, report_type, metrics):
        try:
            analysis = await model_ai_service.analyze(report_type, metrics)
            if isinstance(analysis, dict) and isinstance(analysis.get("suggestions"), list):
                analysis["suggestions"] = [
                    _suggestion(item) if isinstance(item, str) else item
                    for item in analysis["suggestions"]
                ]
            validated = _validate(analysis)
            if validated:
                return validated
        except Exception as exc:
            logger.warning("Model report analysis failed: report_type=%s error=%s", report_type, exc)
        try:
            return _validate(_mock_analysis(report_type, metrics))
        except Exception as exc:
            logger.warning("Report mock analysis failed: report_type=%s error=%s", report_type, exc)
            return None
