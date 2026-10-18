"""M5 智能报告模块 — 模拟数据提供器（阶段 1）

生成确定性的虚构数据，覆盖 report_package/03 要求的全部边界场景。
数据带模拟标记、数据更新时间与参考周期；后续真实数据适配器输出同样的
统一报告输入结构（app/schemas/report.py），只替换本提供器。

参考周期：2026-10-12(周一) 00:00 ~ 2026-10-19(下周一) 00:00（北京时间，naive datetime）。
"""
from datetime import date, datetime, timedelta

from app.schemas.report import (
    ComplaintReportInput,
    CustomerReportInput,
    EmployeeDailyReportInput,
    EmployeeInput,
    MockReportDataset,
    PsychReportInput,
)

# 参考周期（自然周，周一至周日；终点开区间）
PERIOD_START = datetime(2026, 10, 12, 0, 0, 0)  # 周一
PERIOD_END = datetime(2026, 10, 19, 0, 0, 0)    # 下周一（开区间）

# 周一 ~ 周五 日期
_MON = date(2026, 10, 12)
_TUE = date(2026, 10, 13)
_WED = date(2026, 10, 14)
_THU = date(2026, 10, 15)
_FRI = date(2026, 10, 16)
_SAT = date(2026, 10, 17)


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    """构造 2026-10 月的北京时间 naive datetime。"""
    return datetime(2026, 10, day, hour, minute, 0)


def _customers() -> list[CustomerReportInput]:
    """客户数据，覆盖 03 文档 §4 客户场景 1-9。

    14 条记录，其中 c13a/c13b 同手机号（去重场景），去重后 13 个唯一客户。
    """
    return [
        # 本期新增（新增时间在周期内），去向=意向（STRONG）
        CustomerReportInput(
            customer_id=1, phone="13800000001", name="客户1", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(13, 9), status_at_period_end="STRONG",
            latest_assessment_at=_dt(13, 10), sg_conclusion="部分符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="意向强烈，跟进中",
        ),
        # 本期新增，去向=意向（NEW），员工首次提交
        CustomerReportInput(
            customer_id=2, phone="13800000002", name="客户2", source_channel="EMPLOYEE_INPUT",
            first_employee_submit_at=_dt(13, 10), status_at_period_end="NEW",
            latest_assessment_at=_dt(13, 11), sg_conclusion="符合", de_conclusion="不符合",
            owner_employee_id=1, follow_up_summary="刚录入",
        ),
        # 本期新增，去向=意向（FOLLOWING），画像信息不足
        CustomerReportInput(
            customer_id=3, phone="13800000003", name="客户3", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(14, 9), status_at_period_end="FOLLOWING",
            latest_assessment_at=_dt(14, 10), sg_conclusion="信息不足", de_conclusion="信息不足",
            owner_employee_id=2, follow_up_summary="跟进中",
        ),
        # 本期新增，去向=已签约（SIGNED）
        CustomerReportInput(
            customer_id=4, phone="13800000004", name="客户4", source_channel="CS_LEAD",
            first_register_login_at=_dt(14, 10), status_at_period_end="SIGNED",
            latest_assessment_at=_dt(14, 11), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="已签约",
        ),
        # 本期新增，去向=已入学（ENROLLED）
        CustomerReportInput(
            customer_id=5, phone="13800000005", name="客户5", source_channel="EMPLOYEE_INPUT",
            first_employee_submit_at=_dt(15, 9), status_at_period_end="ENROLLED",
            latest_assessment_at=_dt(15, 10), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=2, follow_up_summary="已入学",
        ),
        # 本期新增，去向=已流失（自动流失）
        CustomerReportInput(
            customer_id=6, phone="13800000006", name="客户6", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(15, 10), status_at_period_end="LOST", status_source="auto",
            latest_assessment_at=_dt(15, 11), sg_conclusion="不符合", de_conclusion="不符合",
            owner_employee_id=1, follow_up_summary="自动流失",
        ),
        # 本期新增，去向=已流失（人工流失），无研判结果 -> 画像信息不足（未完成研判）
        CustomerReportInput(
            customer_id=7, phone="13800000007", name="客户7", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(16, 9), status_at_period_end="LOST", status_source="manual",
            latest_assessment_at=None, sg_conclusion=None, de_conclusion=None,
            owner_employee_id=2, follow_up_summary="人工流失",
        ),
        # 本期新增，去向=意向（NEW），画像不符合/信息不足
        CustomerReportInput(
            customer_id=8, phone="13800000008", name="客户8", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(16, 10), status_at_period_end="NEW",
            latest_assessment_at=_dt(16, 11), sg_conclusion="不符合", de_conclusion="部分符合",
            owner_employee_id=1, follow_up_summary="新录入",
        ),
        # 回流客户：新增时间在周期外，不计入本期新增
        CustomerReportInput(
            customer_id=9, phone="13800000009", name="客户9", source_channel="WEBSITE_REGISTER",
            first_register_login_at=datetime(2026, 9, 5, 10, 0, 0), status_at_period_end="NEW",
            reflowed=True, latest_assessment_at=_dt(13, 9), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="回流客户",
        ),
        # 老客户（非本期新增），期末已签约
        CustomerReportInput(
            customer_id=10, phone="13800000010", name="客户10", source_channel="EMPLOYEE_INPUT",
            first_employee_submit_at=datetime(2026, 9, 10, 10, 0, 0), status_at_period_end="SIGNED",
            latest_assessment_at=datetime(2026, 9, 12, 10, 0, 0), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="老客户已签约",
        ),
        # 老客户，期末已流失（自动）
        CustomerReportInput(
            customer_id=11, phone="13800000011", name="客户11", source_channel="WEBSITE_REGISTER",
            first_register_login_at=datetime(2026, 8, 1, 10, 0, 0), status_at_period_end="LOST",
            status_source="auto", latest_assessment_at=datetime(2026, 8, 5, 10, 0, 0),
            sg_conclusion="不符合", de_conclusion="不符合", owner_employee_id=2, follow_up_summary="老客户流失",
        ),
        # 老客户，期末已入学
        CustomerReportInput(
            customer_id=12, phone="13800000012", name="客户12", source_channel="WEBSITE_REGISTER",
            first_register_login_at=datetime(2026, 7, 1, 10, 0, 0), status_at_period_end="ENROLLED",
            latest_assessment_at=datetime(2026, 7, 5, 10, 0, 0), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="老客户已入学",
        ),
        # 去重场景：同一手机号两条记录（网站注册 + 员工提交），取更早新增时间
        CustomerReportInput(
            customer_id=13, phone="13800000013", name="客户13-网站", source_channel="WEBSITE_REGISTER",
            first_register_login_at=_dt(17, 9), status_at_period_end="NEW",
            latest_assessment_at=_dt(17, 9, 30), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="网站渠道",
        ),
        CustomerReportInput(
            customer_id=14, phone="13800000013", name="客户13-员工", source_channel="EMPLOYEE_INPUT",
            first_employee_submit_at=_dt(17, 8), status_at_period_end="FOLLOWING",
            latest_assessment_at=_dt(17, 9, 30), sg_conclusion="符合", de_conclusion="符合",
            owner_employee_id=1, follow_up_summary="员工渠道（更早）",
        ),
    ]


def _employees() -> list[EmployeeInput]:
    """在职员工花名册：5 人，e1/e2 咨询部、e3/e4 教务部、e5 市场部。"""
    dept = {1: "咨询部", 2: "咨询部", 3: "教务部", 4: "教务部", 5: "市场部"}
    return [EmployeeInput(employee_id=i, department=dept[i], employment_status="active") for i in range(1, 6)]


def _daily_reports() -> list[EmployeeDailyReportInput]:
    """员工日报数据，覆盖 03 文档 §4 员工场景 1-5。

    在职员工 5 人：e1/e2 咨询部，e3/e4 教务部，e5 市场部。
    """
    dept = {1: "咨询部", 2: "咨询部", 3: "教务部", 4: "教务部", 5: "市场部"}
    rows: list[EmployeeDailyReportInput] = []

    def add(eid: int, rdate: date, submitted: datetime, content: str) -> None:
        rows.append(EmployeeDailyReportInput(
            employee_id=eid, department=dept[eid], report_date=rdate,
            submitted_at=submitted, content=content,
        ))

    # 周一（10-12）：e1/e2/e3/e5 提交，e4 未交
    add(1, _MON, _dt(12, 17), "跟进客户A，完成意向登记")
    add(2, _MON, _dt(12, 18), "处理客户B咨询")
    add(3, _MON, _dt(12, 17, 30), "安排本周课程")
    add(5, _MON, _dt(12, 18, 30), "市场推广方案")
    # e1 同日重复提交（去重场景：同一员工同一日期最多计一次）
    add(1, _MON, _dt(12, 20), "重复提交，应被去重")

    # 周二（10-13）：e1/e3/e4/e5 提交，e2 未交；e2 补交周一
    add(1, _TUE, _dt(13, 17), "周二跟进")
    add(3, _TUE, _dt(13, 17), "周二教务")
    add(4, _TUE, _dt(13, 17), "周二学生事务")
    add(5, _TUE, _dt(13, 17), "周二市场")
    add(2, _MON, _dt(13, 9), "补交周一日报")  # 补交归周一

    # 周三（10-14）：全员提交
    for eid in (1, 2, 3, 4, 5):
        add(eid, _WED, _dt(14, 17), f"周三工作进展{eid}")

    # 周四（10-15）：e1/e3/e4 提交，e2/e5 未交
    add(1, _THU, _dt(15, 17), "周四客户跟进")
    add(3, _THU, _dt(15, 17), "周四教务")
    add(4, _THU, _dt(15, 17), "周四学生事务")

    # 周五（10-16）：e1/e2/e3/e5 提交，e4 未交
    add(1, _FRI, _dt(16, 17), "周五总结")
    add(2, _FRI, _dt(16, 17), "周五客户")
    add(3, _FRI, _dt(16, 17), "周五教务")
    add(5, _FRI, _dt(16, 17), "周五市场")

    # 周末（10-17 周六）：e1 提交，不计应交/未交，内容进入工作摘要
    add(1, _SAT, _dt(17, 10), "周末跟进客户C")

    return rows


def _psych_records() -> list[PsychReportInput]:
    """心理记录数据，覆盖 03 文档 §4 心理场景 1-5。

    本周有心理记录的学生：s1/s2/s3/s4（s2 有两条记录，按学生去重）。
    """
    return [
        PsychReportInput(student_id=1, record_at=_dt(13, 9), emotion_tag="焦虑", risk_level="高",
                         feedback_summary="考前焦虑", feedback_raw="最近考试很多，晚上睡不着",
                         responsible_employee_id=1, student_name="李娜", student_contact="13800000001"),
        PsychReportInput(student_id=2, record_at=_dt(13, 10), emotion_tag="压力", risk_level="中",
                         feedback_summary="学业压力", feedback_raw="课程进度有点跟不上",
                         responsible_employee_id=2, student_name="王强", student_contact="13800000002"),
        PsychReportInput(student_id=2, record_at=_dt(14, 10), emotion_tag="压力", risk_level="中",
                         feedback_summary="学业压力（第二次记录，应去重）", feedback_raw="还是有点压力",
                         responsible_employee_id=2, student_name="王强", student_contact="13800000002"),
        PsychReportInput(student_id=3, record_at=_dt(15, 10), emotion_tag="平稳", risk_level="低",
                         feedback_summary="状态平稳", feedback_raw="最近状态不错",
                         responsible_employee_id=3, student_name="赵敏", student_contact="13800000003"),
        PsychReportInput(student_id=4, record_at=_dt(16, 10), emotion_tag="低落", risk_level="高",
                         feedback_summary="情绪低落", feedback_raw="有点想家，情绪低落",
                         responsible_employee_id=1, student_name="陈杰", student_contact="13800000004"),
    ]


def _complaints() -> list[ComplaintReportInput]:
    """投诉工单数据，覆盖 03 文档 §4 投诉场景 1-6。

    v6.11.0 口径：类型来源标 `category_source="student"`（学生所选），
    有 AI 分析结果的标 `analysis_status="analyzed"`；t11 故意留「待分析」用于演示。
    t5/t6 为建议/咨询，不计入投诉统计。
    长期未解决边界：截止 10-19 00:00；恰好 7×24h 不算，超过算。
    """
    base = dict(category_source="student", analysis_status="analyzed")
    return [
        # 已响应、已解决、满意
        ComplaintReportInput(ticket_id=1, student_id=1, feedback_type="投诉",
                             submitted_at=_dt(12, 9), first_response_at=_dt(12, 11),
                             resolved_at=_dt(14, 10), status="resolved", satisfaction="满意",
                             content="宿舍空调坏了三天没人修", detail="已经联系宿管两次",
                             student_name="李娜", student_contact="13800000001", **base),
        # 未响应（无首次响应）
        ComplaintReportInput(ticket_id=2, student_id=2, feedback_type="投诉",
                             submitted_at=_dt(13, 9), status="open", satisfaction="未评价",
                             content="课程安排与宣传不符", student_name="王强",
                             student_contact="13800000002", **base),
        # 已响应未解决，提交于 10-06，超过 7×24h -> 长期未解决
        ComplaintReportInput(ticket_id=3, student_id=3, feedback_type="投诉",
                             submitted_at=_dt(6, 9), first_response_at=_dt(6, 11),
                             status="open", satisfaction="未评价",
                             content="退费流程复杂", student_name="赵敏",
                             student_contact="13800000003", **base),
        # 恰好 7×24h（10-12 00:00 提交，截止 10-19 00:00）-> 不算长期未解决，未响应
        ComplaintReportInput(ticket_id=4, student_id=4, feedback_type="投诉",
                             submitted_at=_dt(12, 0), status="open", satisfaction="未评价",
                             content="签证材料指导不到位", student_name="陈杰",
                             student_contact="13800000004", **base),
        # 建议（不计入投诉）
        ComplaintReportInput(ticket_id=5, student_id=5, feedback_type="建议",
                             submitted_at=_dt(12, 10), status="open",
                             content="希望增加德语角活动", **base),
        # 咨询（不计入投诉）
        ComplaintReportInput(ticket_id=6, student_id=6, feedback_type="咨询",
                             submitted_at=_dt(13, 10), status="open",
                             content="咨询新加坡院校截止时间", **base),
        # 已解决、不满意
        ComplaintReportInput(ticket_id=7, student_id=7, feedback_type="投诉",
                             submitted_at=_dt(15, 9), first_response_at=_dt(15, 10),
                             resolved_at=_dt(16, 9), status="resolved", satisfaction="不满意",
                             content="住宿安排与承诺不同", student_name="刘洋",
                             student_contact="13800000007", **base),
        # 超过 7×24h（10-11 23:59 提交）-> 长期未解决
        ComplaintReportInput(ticket_id=8, student_id=8, feedback_type="投诉",
                             submitted_at=_dt(11, 23, 59), status="open", satisfaction="未评价",
                             content="课堂老师频繁更换", student_name="周敏",
                             student_contact="13800000008", **base),
        # AI 判为高风险 -> 特别案例（v6.11.0 起一期无人工复核，AI 判定即成立）
        ComplaintReportInput(ticket_id=9, student_id=9, feedback_type="投诉",
                             submitted_at=_dt(14, 9), first_response_at=_dt(14, 10),
                             status="open", ai_high_risk=True,
                             content="多次投诉同一问题未解决", detail="已第三次反馈",
                             student_name="何静", student_contact="13800000009",
                             owner_id=1, progress="已升级至主管",
                             ai_summary="学生就同一问题多次反馈且未闭环，情绪升级风险高", **base),
        # AI 判为高风险且低满意候选 -> 特别案例（完整详情演示）
        ComplaintReportInput(ticket_id=10, student_id=10, feedback_type="投诉",
                             submitted_at=_dt(14, 10), first_response_at=_dt(14, 11),
                             status="open", ai_low_score=True, ai_high_risk=True,
                             content="承诺的实习岗位未落实", detail="合同附件中有岗位说明",
                             student_name="郭婷", student_contact="13800000010",
                             owner_id=1, progress="已联系学生",
                             ai_summary="涉及招生承诺兑现，属高风险且学生明确表达不满", **base),
        # 待分析工单（AI 未分析）：只计入工单总量，不进投诉/AI 指标
        ComplaintReportInput(ticket_id=11, student_id=11, feedback_type="投诉",
                             submitted_at=_dt(15, 14), status="open",
                             content="（待分析）反馈食堂口味问题",
                             analysis_status="pending", category_source="unknown"),
    ]


def build_mock_dataset(
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> MockReportDataset:
    """构造完整模拟数据包（M5-02.2：支持指定周期）。

    周期缺省时使用参考周期（2026-10-12 ~ 10-19）；指定其它周期时，
    数据集的 period 字段按请求值盖章，样本记录本身不变（确定性样本），
    指标计算按请求周期过滤——非参考周期大部分指标自然为空，属预期行为
    （见 06_后端交付说明V1 风险说明 2）。
    """
    return MockReportDataset(
        data_updated_at=PERIOD_END - timedelta(minutes=1),
        period_start=period_start or PERIOD_START,
        period_end=period_end or PERIOD_END,
        customers=_customers(),
        employees=_employees(),
        daily_reports=_daily_reports(),
        psych_records=_psych_records(),
        complaints=_complaints(),
    )
