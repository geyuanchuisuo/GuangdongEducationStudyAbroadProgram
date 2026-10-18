"""M5 智能报告模块 — PDF 汇总导出（阶段 6）

仅渲染报告内容里的汇总指标与 AI 文字。报告内容本身只存聚合数，
不含客户/学生/投诉的个人敏感信息、原文、处理详情、心理反馈或未复核案例，
因此 PDF 天然脱敏。下载前由接口层校验 MANAGER/ADMIN 权限。
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# 内置 CID 中文字体，无需外部字体文件
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
FONT = "STSong-Light"

_STATUS_LABELS = {
    "NEW": "新录入",
    "FOLLOWING": "跟进中",
    "STRONG": "意向强烈",
    "SIGNED": "已签约",
    "ENROLLED": "已入学",
    "LOST": "已流失",
}


def _styles() -> dict:
    return {
        "title": ParagraphStyle("title", fontName=FONT, fontSize=18, leading=24, spaceAfter=10),
        "meta": ParagraphStyle("meta", fontName=FONT, fontSize=9, leading=14, textColor=colors.HexColor("#555555")),
        "h2": ParagraphStyle("h2", fontName=FONT, fontSize=13, leading=18, spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=FONT, fontSize=10, leading=15),
    }


def _src_label(v: str) -> str:
    return "正式" if v == "production" else "模拟"


def _ai_label(v: str, source: str = "") -> str:
    """AI 文字来源标注（M5-10.6 差异字段 ai_source）。"""
    if v != "available":
        return "不可用"
    return {"model": "可用（共用模型网关）", "mock": "可用（模拟数据）"}.get(source, "可用")


def _make_table(data: list[list], col_widths: list[float]) -> Table:
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


_UNAVAILABLE = "数据不可得"


def _val(v, suffix: str = "") -> str:
    """指标渲染：None 显示「数据不可得」，不用 0 冒充（v6.11.0 §2.8）。"""
    if v is None:
        return _UNAVAILABLE
    return f"{v}{suffix}"


def _metric_tables(report_type: str, m: dict) -> list[tuple[str, Table]]:
    """按报告类型生成 (小节标题, 表格) 列表。None 一律显示「数据不可得」。"""
    if report_type == "customer_analysis":
        ov = m.get("status_overview")
        availability = m.get("availability", {})
        out: list[tuple[str, Table]] = []
        if ov is None:
            out.append(("客户状态总览", _make_table(
                [["状态", "说明"], ["期末状态", "数据不可得（M1 无历史时点能力，不用当前值冒充）"]],
                [90, 300],
            )))
        else:
            status_rows = [["状态", "新录入", "跟进中", "意向强烈", "已签约", "已入学", "已流失", "合计"]]
            status_rows.append(["数量", ov["NEW"], ov["FOLLOWING"], ov["STRONG"],
                                ov["SIGNED"], ov["ENROLLED"], ov["LOST"], ov["total"]])
            out.append(("客户状态总览", _make_table(status_rows, [70] + [45] * 6 + [45])))
            summary_rows = [
                ["汇总", "期末意向", "期末成交", "期末流失"],
                ["数量", ov["intent"], ov["converted"], ov["lost"]],
            ]
            out.append(("状态汇总", _make_table(summary_rows, [70, 60, 60, 60])))

        out.append(("本期新增客户", _make_table(
            [["指标", "数值"], ["本期新增（按手机号去重）", _val(m.get("new_this_period"))]],
            [160, 90],
        )))

        outcomes = m.get("new_outcomes")
        if outcomes is None:
            out.append(("本期新增去向", _make_table(
                [["去向", "说明"], ["期末去向", "数据不可得（依赖期末状态）"]], [90, 300])))
        else:
            out.append(("本期新增去向", _make_table([
                ["本期新增去向", "仍意向", "已签约", "已入学", "已流失", "合计"],
                ["数量", outcomes["intent"], outcomes["signed"], outcomes["enrolled"],
                 outcomes["lost"], m.get("new_this_period")],
            ], [80, 55, 55, 55, 55, 45])))

        # 画像四类（v6.11.0：符合/部分符合/不符合/信息不足；分母只计有研判客户）
        profiles = m.get("profiles") or {}
        sg = profiles.get("sg_conclusion")
        de = profiles.get("de_conclusion")
        denom = m.get("profile_denominator") or {}
        if sg is None or de is None:
            reason = "数据不可得（依赖期末状态）" if availability.get("profiles") == "unavailable" else "暂无有效研判"
            out.append(("项目画像", _make_table(
                [["项目画像", "说明"], ["分类", reason]], [90, 300])))
        else:
            profile_rows = [
                ["项目画像", "符合", "部分符合", "不符合", "信息不足", "分母（有研判）"],
                ["新加坡", sg["符合"], sg["部分符合"], sg["不符合"], sg["信息不足"], denom.get("sg_conclusion")],
                ["德国", de["符合"], de["部分符合"], de["不符合"], de["信息不足"], denom.get("de_conclusion")],
            ]
            out.append(("项目画像", _make_table(profile_rows, [70, 50, 60, 55, 55, 90])))
        return out

    if report_type == "complaint_weekly":
        avg = m.get("avg_first_response_seconds")
        avg_h = round(avg / 3600, 1) if avg is not None else _UNAVAILABLE
        maxs = m.get("max_first_response_seconds")
        max_h = round(maxs / 3600, 1) if maxs is not None else _UNAVAILABLE
        rows = [
            ["核心数据", "数值"],
            ["工单总量（含待分析）", _val(m.get("orders_total"))],
            ["待分析工单", _val(m.get("pending_analysis"))],
            ["已完成 AI 分析", _val(m.get("analyzed_count"))],
            ["投诉数（学生所选或 AI 分类）", _val(m.get("new_count"))],
            ["解决数（本周期）", _val(m.get("resolved_in_period"))],
            ["期末未解决数", _val(m.get("open_count"))],
            ["超过七天未解决数", _val(m.get("over7_unresolved"))],
            ["首次响应数量", _val(m.get("first_response_count"))],
            ["未响应数量", _val(m.get("not_responded_count"))],
            ["平均首次响应时长(小时)", avg_h],
            ["最长首次响应时长(小时)", max_h],
            ["低满意度候选（AI）", _val(m.get("low_satisfaction_candidates"))],
            ["高风险候选（AI）", _val(m.get("high_risk_candidates"))],
            ["特别案例（AI 判定）", _val(m.get("special_cases"))],
        ]
        sat = m.get("satisfaction") or {}
        sat_rows = [
            ["满意度（仅学生明确评价）", "满意", "不满意", "未评价"],
            ["数量", _val(sat.get("满意")), _val(sat.get("不满意")), _val(sat.get("未评价"))],
        ]
        return [
            ("核心数据", _make_table(rows, [170, 100])),
            ("满意度", _make_table(sat_rows, [130, 60, 60, 60])),
        ]

    if report_type == "daily_report_summary":
        # M5-07.1 日报拆分：仅期间合计与每日明细，无全周人次、无部门汇总
        days = m["days"]
        total = {
            "should_submit": sum(d["should_submit"] for d in days),
            "submitted": sum(d["submitted"] for d in days),
            "missing": sum(d["missing"] for d in days),
        }
        period_rows = [
            ["期间合计人次", "应提交", "已提交", "未提交"],
            ["数量", total["should_submit"], total["submitted"], total["missing"]],
        ]
        day_rows = [["日期", "应提交", "已提交", "未提交"]]
        for d in days:
            day_rows.append([d["date"], d["should_submit"], d["submitted"], d["missing"]])
        w4 = [90, 70, 70, 70]
        return [
            ("期间合计", _make_table(period_rows, w4)),
            ("每日提交明细", _make_table(day_rows, w4)),
        ]

    if report_type == "weekly_report_summary":
        total = m["week_total"]
        week_rows = [
            ["全周人次", "应提交", "已提交", "未提交"],
            ["数量", total["should_submit"], total["submitted"], total["missing"]],
        ]
        day_rows = [["日期", "应提交", "已提交", "未提交"]]
        for d in m["days"]:
            day_rows.append([d["date"], d["should_submit"], d["submitted"], d["missing"]])
        dept_rows = [["部门", "应提交", "已提交", "未提交"]]
        for dept, v in m["departments"].items():
            dept_rows.append([dept, v["should_submit"], v["submitted"], v["missing"]])
        w4 = [90, 70, 70, 70]
        return [
            ("全周人次", _make_table(week_rows, w4)),
            ("每日提交明细", _make_table(day_rows, w4)),
            ("部门汇总", _make_table(dept_rows, w4)),
        ]

    if report_type == "psych_weekly":
        risk = m["risk"]
        rows = [
            ["心理周报", "覆盖学生", "高风险", "中风险", "低风险"],
            ["数量", m["covered_students"], risk["高"], risk["中"], risk["低"]],
        ]
        return [("总体态势", _make_table(rows, [80, 70, 60, 60, 60]))]

    return []


def generate_report_pdf(content: dict) -> bytes:
    buf = BytesIO()
    st = _styles()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    story = []

    h = content.get("header", {})
    # M5-08.5：所有进入 Paragraph 的文本（含 AI 生成的文字）必须 XML 转义，
    # 否则含 &/< 的文案会导致 reportlab 解析异常
    story.append(Paragraph(escape(h.get("report_name", "智能报告")), st["title"]))
    period = f"{h.get('period_start', '')[:10]} ~ {h.get('period_end', '')[:10]}"
    meta = (
        f"周期：{escape(period)}　|　版本：V{int(h.get('version', 1))}　|　"
        f"生成时间：{escape(h.get('generated_at', '')[:19])}　|　"
        f"数据来源：{_src_label(h.get('data_source_status', 'mock'))}　|　"
        f"AI：{_ai_label(content.get('ai_status', 'unavailable'), content.get('ai_source', ''))}"
    )
    story.append(Paragraph(meta, st["meta"]))
    story.append(Spacer(1, 8))

    if content.get("summary"):
        story.append(Paragraph("本期摘要", st["h2"]))
        story.append(Paragraph(escape(str(content["summary"])), st["body"]))

    story.append(Paragraph("核心指标", st["h2"]))
    for title, table in _metric_tables(h.get("report_type", ""), content.get("metrics", {})):
        story.append(Paragraph(escape(title), st["h2"]))
        story.append(table)

    # 上一周期对比（v6.11.0 §2.3：客户月报默认与上一个自然月比较）
    comp = content.get("comparison")
    if comp:
        story.append(Paragraph("上一周期对比", st["h2"]))
        if comp.get("status") != "ok":
            story.append(Paragraph(escape(f"不可比：{comp.get('note', '上一周期数据不可得')}"), st["body"]))
        else:
            prev = (comp.get("metrics") or {}).get("status_overview") or {}
            story.append(Paragraph(escape(
                f"对比周期：{comp.get('period_start', '')[:10]} ~ {comp.get('period_end', '')[:10]}；"
                f"上期新增客户 {_val((comp.get('metrics') or {}).get('new_this_period'))} 名；"
                f"上期期末意向 {_val(prev.get('intent'))} 名、成交 {_val(prev.get('converted'))} 名、"
                f"流失 {_val(prev.get('lost'))} 名。"
            ), st["body"]))

    # 投诉特别案例完整详情（v6.11.0 §2.6：仅 MANAGER/ADMIN 可下载）
    cases = content.get("special_cases")
    if cases:
        story.append(Paragraph("投诉特别案例（AI 判定，完整详情）", st["h2"]))
        for c in cases:
            story.append(Paragraph(escape(
                f"工单 #{c.get('ticket_id')}｜学生：{c.get('student_name') or '—'}｜"
                f"联系方式：{c.get('student_contact') or '—'}｜状态：{c.get('status')}｜"
                f"满意度：{c.get('satisfaction')}"
            ), st["body"]))
            if c.get("content"):
                story.append(Paragraph(escape(f"工单内容：{c['content']}"), st["body"]))
            if c.get("detail"):
                story.append(Paragraph(escape(f"补充说明：{c['detail']}"), st["body"]))
            if c.get("ai_summary"):
                story.append(Paragraph(escape(f"AI 归纳理由：{c['ai_summary']}"), st["body"]))
            if c.get("progress"):
                story.append(Paragraph(escape(f"处理过程：{c['progress']}"), st["body"]))
            story.append(Spacer(1, 4))

    if content.get("trend"):
        story.append(Paragraph("趋势与对比", st["h2"]))
        story.append(Paragraph(escape(str(content["trend"])), st["body"]))

    if content.get("analysis"):
        story.append(Paragraph("业务分析", st["h2"]))
        story.append(Paragraph(escape(str(content["analysis"])), st["body"]))

    if content.get("suggestions"):
        story.append(Paragraph("建议事项", st["h2"]))
        for s in content["suggestions"]:
            story.append(Paragraph(f"• {escape(str(s.get('content', '')))}", st["body"]))

    story.append(Paragraph("数据与口径说明", st["h2"]))
    story.append(Paragraph(escape(content.get("data_notes", "")), st["body"]))

    story.append(Spacer(1, 10))
    if content.get("special_cases"):
        story.append(Paragraph(
            "本报告含投诉特别案例完整详情，仅限 MANAGER/ADMIN 访问与下载；请勿外传，注意隐私风险。",
            st["meta"]))
    else:
        story.append(Paragraph("本报告为脱敏汇总，不含个人敏感信息。", st["meta"]))

    doc.build(story)
    return buf.getvalue()
