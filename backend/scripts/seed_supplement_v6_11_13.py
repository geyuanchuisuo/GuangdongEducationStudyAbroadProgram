#!/usr/bin/env python3
"""v6.11.13：种子数据补充脚本——补齐「造好的数据 vs 现有字段」差异（数据审计缺口）

审计结论（2026-10-19）：schema 演进后多列/多表无数据覆盖（customer 8 研判画像字段全 NULL、
研判 JSON 证据全 NULL、cs_recommend_log / ticket_ai_analysis / ai_report_attachment 空表等 16 类）。
本脚本以真实业务数据补齐缺口：
  - 固定随机种子 random.seed(20261019)，可复现
  - 幂等：只填「当前为 NULL」的列；新表按空表守卫插入，重跑不重复
  - 不动已有数据、不重建库（与 seed_data.py 的 drop_all+seed 是两回事，禁止混用）
用法：backend\.venv\Scripts\python.exe backend/scripts/seed_supplement_v6_11_13.py
"""
import json
import os
import random
from datetime import datetime, timedelta

import pymysql

random.seed(20261019)


def _mysql_conn():
    """连接目标：默认宿主机映射 127.0.0.1:59000（本地运行）；
    容器内/自定义环境用 SEED_MYSQL_* 环境变量覆盖（seed_all 自动注入时按 DATABASE_URL 传入）。
    """
    return pymysql.connect(
        host=os.environ.get("SEED_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("SEED_MYSQL_PORT", "59000")),
        user=os.environ.get("SEED_MYSQL_USER", "root"),
        password=os.environ.get("SEED_MYSQL_PASSWORD", "420821"),
        database=os.environ.get("SEED_MYSQL_DB", "GuangdongEducationStudyAbroadProgram"),
        charset="utf8mb4",
    )


conn = _mysql_conn()
cur = conn.cursor()
T0 = datetime(2026, 10, 18, 18, 0, 0)


def ts(days_back: int, hour: int = 10) -> str:
    return (T0 - timedelta(days=days_back)).replace(hour=hour, minute=random.randint(0, 59)).strftime("%Y-%m-%d %H:%M:%S")


def rows(sql: str, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def pick(seq):
    return random.choice(seq)


ECONOMY = ["年收入10万以下", "年收入15万左右", "年收入20-30万", "年收入30-50万", "年收入50万以上", "个体经营，年收入约25万", "家庭年收入约40万"]
NEEDS = ["本科升学", "硕士升学", "职业培训+海外就业", "语言培训", "高中留学", "专升本", "短期研学交流", "就业指导"]
INTENT = ["意向德国，双元制本科", "意向德国，机械工程硕士", "意向德国，护理双元制", "意向新加坡，商科硕士", "意向新加坡，计算机本科", "暂无明确意向，多方了解", "意向德国，已开始学德语"]
GERMAN = ["零基础", "A1", "A2", "B1", "B2", "德福12分"]
ENGLISH = ["零基础", "四级水平", "六级水平", "雅思5.5", "雅思6.0", "雅思6.5", "口语良好"]
CLOSED = ["接受", "不接受", "视情况而定"]
CRIMINAL = ["无", "无犯罪记录", "无（已开具证明）"]
BELT = ["不了解", "听说过", "了解", "熟悉，关注德国就业政策"]

# ── 1. customer：8 研判画像字段 + wechat + 流失/回流痕迹 ──────────────
n = 0
for (cid, name, status) in rows("SELECT id, name, status FROM customer WHERE economy IS NULL"):
    cur.execute(
        """UPDATE customer SET wechat=%s, economy=%s, needs=%s, study_intent=%s, german_ability=%s,
           english_ability=%s, closed_training=%s, criminal_record=%s, belt_and_road=%s WHERE id=%s""",
        (f"wx_{(name or 'user')[-3:]}{cid}", pick(ECONOMY), pick(NEEDS), pick(INTENT), pick(GERMAN),
         pick(ENGLISH), pick(CLOSED), pick(CRIMINAL), pick(BELT), cid),
    )
    if status == "LOST":
        cur.execute("UPDATE customer SET auto_churned=%s, churned_at=%s WHERE id=%s AND churned_at IS NULL",
                    (random.choice([0, 1]), ts(random.randint(5, 60)), cid))
    n += 1
print(f"1. customer 研判字段补齐: {n} 行")

# ── 2. customer_assessment：5 个研判 JSON 证据 + dify_run_id ──────────
CONC = ["matched", "partial", "not_matched", "pending"]
n = 0
for (aid,) in rows("SELECT id FROM customer_assessment WHERE dimensions_json IS NULL"):
    sg, de = random.choice(CONC), random.choice(CONC)
    dims = {"economy": {"value": pick(ECONOMY), "evidence": "访谈记录"}, "language": {"value": f"{pick(GERMAN)}/{pick(ENGLISH)}", "evidence": "自述+测试"},
            "intent": {"value": pick(INTENT), "evidence": "需求调研表"}}
    matched = [{"name": "德国双元制本科", "match": sg}, {"name": "新加坡商科硕士", "match": de}]
    rec = [{"name": "德国双元制本科", "reason": "经济与语言条件符合，意愿明确"}] if sg == "matched" else [{"name": "新加坡商科硕士", "reason": "部分条件符合，建议补充语言成绩"}]
    missing = [] if random.random() < 0.5 else ["德语官方成绩", "资金证明"]
    conflicts = [] if random.random() < 0.7 else ["意向国家与预算不完全匹配"]
    cur.execute(
        """UPDATE customer_assessment SET dimensions_json=%s, matched_programs_json=%s, recommended_json=%s,
           missing_info_json=%s, conflicts_json=%s, dify_run_id=%s WHERE id=%s""",
        (json.dumps(dims, ensure_ascii=False), json.dumps(matched, ensure_ascii=False), json.dumps(rec, ensure_ascii=False),
         json.dumps(missing, ensure_ascii=False), json.dumps(conflicts, ensure_ascii=False),
         f"run-{random.randint(10**7, 10**8-1):x}" if random.random() < 0.4 else None, aid),
    )
    n += 1
print(f"2. customer_assessment 研判 JSON 补齐: {n} 行")

# ── 3. cs_recommend_log：空表补 60 条推荐日志 ─────────────────────────
n = 0
if rows("SELECT COUNT(*) FROM cs_recommend_log")[0][0] == 0:
    sessions = [r[0] for r in rows("SELECT id FROM cs_chat_session ORDER BY id LIMIT 80")]
    customers = [r[0] for r in rows("SELECT id FROM customer ORDER BY id LIMIT 80")]
    courses = [r[0] for r in rows("SELECT id FROM course_project")]
    events = [r[0] for r in rows("SELECT id FROM event_lecture")]
    cnames = [r[0] for r in rows("SELECT project_name FROM course_project")]
    enames = [r[0] for r in rows("SELECT event_name FROM event_lecture")] if rows("SELECT COUNT(*) FROM event_lecture")[0][0] else ["留学说明会"]
    for i in range(60):
        is_course = random.random() < 0.65
        cur.execute(
            "INSERT INTO cs_recommend_log (session_id, customer_id, course_id, event_id, recommendation_type, item_name, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (pick(sessions), pick(customers), pick(courses) if is_course else None, None if is_course else pick(events),
             "course" if is_course else "event", pick(cnames) if is_course else pick(enames), ts(random.randint(1, 45))),
        )
        n += 1
print(f"3. cs_recommend_log 新增: {n} 行")

# ── 4. ticket_ai_analysis：空表补 55 条 AI 分析 ────────────────────────
n = 0
if rows("SELECT COUNT(*) FROM ticket_ai_analysis")[0][0] == 0:
    tickets = [r[0] for r in rows("SELECT id FROM student_feedback_ticket ORDER BY id LIMIT 55")]
    for tid in tickets:
        cat = random.choices(["投诉", "建议", "咨询"], weights=[0.5, 0.3, 0.2])[0]
        ok = random.random() < 0.85
        cur.execute(
            """INSERT INTO ticket_ai_analysis (ticket_id, category, low_satisfaction_candidate, high_risk, summary,
               special_reason, model_source, prompt_version, raw_output, status, error_message, analyzed_at, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tid, cat, cat == "投诉" and random.random() < 0.4, random.random() < 0.15,
             f"学生对{random.choice(['课程安排', '宿舍管理', '缴费流程', '考试安排', '老师答疑'])}提出{cat}，建议跟进处理。",
             "涉及安全或群体情绪，列入特别案例" if random.random() < 0.15 else None,
             "dify:智能报告", "v1.2", json.dumps({"category": cat}, ensure_ascii=False) if ok else None,
             "succeeded" if ok else "failed", None if ok else "模型调用超时", ts(random.randint(1, 20)) if ok else None, ts(random.randint(1, 20))),
        )
        n += 1
print(f"4. ticket_ai_analysis 新增: {n} 行")

# ── 5. ai_report_attachment：空表补 12 条报告附件 ──────────────────────
n = 0
if rows("SELECT COUNT(*) FROM ai_report_attachment")[0][0] == 0:
    reports = [r[0] for r in rows("SELECT id FROM ai_report ORDER BY id LIMIT 12")]
    for rid in reports:
        cur.execute("INSERT INTO ai_report_attachment (report_id, file_path, file_type, created_at) VALUES (%s,%s,%s,%s)",
                    (rid, f"./storage_data/reports/report_{rid}.pdf", "pdf", ts(random.randint(1, 30))))
        n += 1
print(f"5. ai_report_attachment 新增: {n} 行")

# ── 6. cs_chat_message：slots_json / card_data / tokens / citations ───
n = 0
for (mid, role) in rows("SELECT id, role FROM cs_chat_message WHERE slots_json IS NULL AND card_data IS NULL AND tokens IS NULL ORDER BY id LIMIT 120"):
    if role == "user" and random.random() < 0.35:
        slots = {"name": random.choice(["张同学", "李同学", "王同学"]), "age": random.randint(18, 30), "study_intent": pick(INTENT)}
        cur.execute("UPDATE cs_chat_message SET slots_json=%s WHERE id=%s AND slots_json IS NULL", (json.dumps(slots, ensure_ascii=False), mid))
    elif role == "assistant":
        if random.random() < 0.3:
            card = {"type": "faq", "faq": {"question": "公司简称是什么？", "answer": "简称\"粤教服务\""}}
            cur.execute("UPDATE cs_chat_message SET card_data=%s, tokens=%s WHERE id=%s AND card_data IS NULL",
                        (json.dumps(card, ensure_ascii=False), random.randint(80, 600), mid))
        else:
            cur.execute("UPDATE cs_chat_message SET tokens=%s WHERE id=%s AND tokens IS NULL", (random.randint(60, 500), mid))
    n += 1
print(f"6. cs_chat_message 槽位/卡片/tokens 补齐: {n} 行")

# ── 7. cs_chat_session：intent_summary / tags_json / dify_conversation_id
n = 0
for (sid,) in rows("SELECT id FROM cs_chat_session WHERE intent_summary IS NULL ORDER BY id LIMIT 90"):
    cur.execute("UPDATE cs_chat_session SET intent_summary=%s, tags_json=%s, dify_conversation_id=%s WHERE id=%s",
                (f"咨询{pick(NEEDS)}相关{pick(['政策', '费用', '流程', '课程'])}",
                 json.dumps(random.sample(["留学咨询", "课程咨询", "费用咨询", "活动咨询", "投诉建议"], 2), ensure_ascii=False),
                 f"conv-{random.randint(10**6, 10**7-1):x}", sid))
    n += 1
print(f"7. cs_chat_session 摘要/标签补齐: {n} 行")

# ── 8. student_academic：description + 提醒痕迹 ────────────────────────
n = 0
for (aid,) in rows("SELECT id FROM student_academic WHERE description IS NULL"):
    if random.random() < 0.8:
        cur.execute("UPDATE student_academic SET description=%s WHERE id=%s",
                    (f"{pick(['完成', '推进中', '待提交'])}{random.choice(['阶段作业', '实验报告', '论文提纲', '预习任务'])}，围绕{random.choice(['德语写作', '数学建模', '专业导论', '口语训练'])}。", aid))
    if random.random() < 0.5:
        cur.execute("UPDATE student_academic SET reminder_sent=%s, reminder_time=%s WHERE id=%s AND reminder_sent=0",
                    (1, ts(random.randint(1, 15), 9), aid))
    n += 1
print(f"8. student_academic description/提醒补齐: {n} 行")

# ── 9. student_application_progress：notes / operator_id ───────────────
emp_ids = [r[0] for r in rows("SELECT id FROM sys_user WHERE user_type IN ('EMPLOYEE','MANAGER') ORDER BY id LIMIT 20")]
n = 0
for (pid,) in rows("SELECT id FROM student_application_progress WHERE notes IS NULL"):
    if random.random() < 0.75:
        cur.execute("UPDATE student_application_progress SET notes=%s, operator_id=%s WHERE id=%s",
                    (f"{random.choice(['材料已收齐', '等待语言成绩', '校方已受理', '签证材料准备中', '已预约面签'])}。", pick(emp_ids), pid))
    n += 1
print(f"9. student_application_progress notes 补齐: {n} 行")

# ── 10. student_feedback_ticket：已办工单补 solution ───────────────────
n = 0
for (tid, status) in rows("SELECT id, status FROM student_feedback_ticket WHERE solution IS NULL"):
    if any(k in (status or "") for k in ("已", "完成", "resolved", "closed")):
        cur.execute("UPDATE student_feedback_ticket SET solution=%s WHERE id=%s",
                    (f"已{random.choice(['联系学生说明情况并调整安排', '协调任课老师加课答疑', '退还相关费用并致歉', '更新系统流程并公告'])}，学生表示满意。", tid))
        n += 1
print(f"10. student_feedback_ticket solution 补齐: {n} 行")

# ── 11. student_psych_alert：已办预警补 handled_action / handled_at ───
n = 0
for (aid, status) in rows("SELECT id, status FROM student_psych_alert WHERE handled_action IS NULL"):
    if not any(k in (status or "") for k in ("未处理", "open", "pending")):
        act = random.choice(["communicated", "referred", "resolved"])
        cur.execute("UPDATE student_psych_alert SET handled_action=%s, handled_at=%s WHERE id=%s",
                    (act, ts(random.randint(1, 25), 15), aid))
        n += 1
print(f"11. student_psych_alert 处理痕迹补齐: {n} 行")

# ── 12. employee_org：组织树 parent_id + leader_id ─────────────────────
orgs = rows("SELECT id FROM employee_org ORDER BY id")
mgrs = [r[0] for r in rows("SELECT id FROM sys_user WHERE user_type='MANAGER' ORDER BY id LIMIT 10")]
n = 0
if orgs:
    root = orgs[0][0]
    for (oid,) in orgs:
        if oid != root:
            cur.execute("UPDATE employee_org SET parent_id=%s WHERE id=%s AND parent_id IS NULL", (root, oid))
            n += 1
    for i, (oid,) in enumerate(orgs):
        if mgrs:
            cur.execute("UPDATE employee_org SET leader_id=%s WHERE id=%s AND leader_id IS NULL", (mgrs[i % len(mgrs)], oid))
print(f"12. employee_org 组织树/负责人补齐: {n} 行")

# ── 13. employee_todo：description / related_type / related_id ─────────
n = 0
for (tid,) in rows("SELECT id FROM employee_todo WHERE description IS NULL ORDER BY id LIMIT 140"):
    cur.execute("UPDATE employee_todo SET description=%s, related_type=%s, related_id=%s WHERE id=%s",
                (f"{random.choice(['跟进', '回访', '整理', '准备'])}{random.choice(['客户资料', '签约材料', '课程反馈', '月度总结'])}。",
                 random.choice(["customer", "approval", "report", None]), random.randint(1, 150) if random.random() < 0.7 else None, tid))
    n += 1
print(f"13. employee_todo 描述/关联补齐: {n} 行")

# ── 14. course_project：target_audience ────────────────────────────────
n = 0
for (cid,) in rows("SELECT id FROM course_project WHERE target_audience IS NULL"):
    cur.execute("UPDATE course_project SET target_audience=%s WHERE id=%s",
                (random.choice(["高中毕业生", "本科在读/毕业生", "在职人士", "专升本学生", "全体学生", "18-28岁有留学意向者"]), cid))
    n += 1
print(f"14. course_project target_audience 补齐: {n} 行")

# ── 15. pending_lead：source_session_id / merged_customer_id ───────────
sess = [r[0] for r in rows("SELECT id FROM cs_chat_session ORDER BY id LIMIT 15")]
cust = [r[0] for r in rows("SELECT id FROM customer ORDER BY id LIMIT 40")]
n = 0
for i, (lid, status) in enumerate(rows("SELECT id, status FROM pending_lead WHERE source_session_id IS NULL")):
    cur.execute("UPDATE pending_lead SET source_session_id=%s, merged_customer_id=%s WHERE id=%s",
                (sess[i % len(sess)] if sess else None,
                 cust[i % len(cust)] if (cust and any(k in (status or "") for k in ("merged", "已合并", "merged"))) else None, lid))
    n += 1
print(f"15. pending_lead 来源/合并补齐: {n} 行")

# ── 16. sys_notification：related_type / related_id ────────────────────
n = 0
for (nid, typ) in rows("SELECT id, type FROM sys_notification WHERE related_type IS NULL ORDER BY id LIMIT 80"):
    rel = {"approval": "approval_instance", "report": "ai_report", "complaint": "student_feedback_ticket"}.get(typ, random.choice(["approval_instance", "ai_report", "event_lecture"]))
    cur.execute("UPDATE sys_notification SET related_type=%s, related_id=%s WHERE id=%s", (rel, random.randint(1, 150), nid))
    n += 1
print(f"16. sys_notification 关联补齐: {n} 行")

# ── 17. daily_report_annotation：补批示至 ~45 条 ───────────────────────
n = 0
cnt = rows("SELECT COUNT(*) FROM daily_report_annotation")[0][0]
if cnt < 45 and mgrs:
    reports = [r[0] for r in rows("SELECT id FROM employee_daily_report ORDER BY id")]
    for rid in random.sample(reports, min(45 - cnt, len(reports))):
        if rows("SELECT COUNT(*) FROM daily_report_annotation WHERE report_id=%s", (rid,))[0][0] == 0:
            cur.execute("INSERT INTO daily_report_annotation (report_id, manager_id, content, create_time) VALUES (%s,%s,%s,%s)",
                        (rid, pick(mgrs), random.choice(["进展不错，注意跟进客户需求。", "日报内容再具体一些，量化产出。", "该客户优先级提高，本周内完成回访。", "按计划推进，有风险及时上报。"]), ts(random.randint(1, 30), 17)))
            n += 1
print(f"17. daily_report_annotation 新增: {n} 行")

# ── 18. 精细化：引用/会话元数据/合并标记/权限/关联学业 ─────────────────
n = 0
for (mid,) in rows("SELECT id FROM cs_chat_message WHERE role='assistant' AND citations_json IS NULL ORDER BY id LIMIT 30"):
    cites = [{"doc": random.choice(["课程项目库", "活动讲座库", "FAQ速查表"]), "slice": f"{random.choice(['德国双元制', '新加坡商科', '费用说明', '报名流程'])}#{random.randint(1, 40)}"} for _ in range(random.randint(1, 2))]
    cur.execute("UPDATE cs_chat_message SET citations_json=%s WHERE id=%s AND citations_json IS NULL", (json.dumps(cites, ensure_ascii=False), mid))
    n += 1
print(f"18. cs_chat_message citations 补齐: {n} 行")

n = 0
for (sid,) in rows("SELECT id FROM cs_chat_session WHERE metadata IS NULL ORDER BY id LIMIT 70"):
    cur.execute("UPDATE cs_chat_session SET metadata=%s WHERE id=%s AND metadata IS NULL",
                (json.dumps({"channel": random.choice(["web", "wechat", "app"]), "entry": random.choice(["公开客服", "学生端助手", "员工端助手"])}, ensure_ascii=False), sid))
    n += 1
print(f"19. cs_chat_session metadata 补齐: {n} 行")

n = 0
cust = [r[0] for r in rows("SELECT id FROM customer ORDER BY id LIMIT 40")]
for (lid,) in rows("SELECT id FROM pending_lead WHERE merged_customer_id IS NULL AND (status NOT IN ('pending') OR id %% 3 = 0) ORDER BY id"):
    if cust:
        cur.execute("UPDATE pending_lead SET merged_customer_id=%s, status=%s WHERE id=%s AND merged_customer_id IS NULL",
                    (pick(cust), "merged", lid))
        n += 1
print(f"20. pending_lead 合并标记补齐: {n} 行")

n = 0
acad = [r[0] for r in rows("SELECT id FROM student_academic ORDER BY id LIMIT 60")]
for (sid,) in rows("SELECT id FROM student_admin_service WHERE related_academic_id IS NULL ORDER BY id LIMIT 40"):
    if acad and random.random() < 0.6:
        cur.execute("UPDATE student_admin_service SET related_academic_id=%s WHERE id=%s AND related_academic_id IS NULL", (pick(acad), sid))
        n += 1
print(f"21. student_admin_service 关联学业补齐: {n} 行")

n = 0
PERMS = {
    "ADMIN": ["system:manage", "user:manage", "report:view", "report:export", "approval:manage"],
    "MANAGER": ["report:view", "report:export", "approval:manage", "employee:manage", "customer:view"],
    "EMPLOYEE": ["customer:edit", "report:daily", "todo:view"],
}
for (uid, ut) in rows("SELECT id, user_type FROM sys_user WHERE permissions IS NULL AND user_type IN ('ADMIN','MANAGER','EMPLOYEE') ORDER BY id LIMIT 60"):
    cur.execute("UPDATE sys_user SET permissions=%s WHERE id=%s AND permissions IS NULL", (json.dumps(PERMS[ut], ensure_ascii=False), uid))
    n += 1
print(f"22. sys_user permissions 补齐: {n} 行")

n = 0
REASONS = ["涉及安全或群体情绪，列入特别案例", "连续多日同类投诉，需专项复盘", "涉及退费争议，转人工复核", "学生情绪激烈，建议优先回访"]
for (aid, cid) in rows("SELECT id, ticket_id FROM ticket_ai_analysis WHERE special_reason IS NOT NULL ORDER BY id"):
    cur.execute("UPDATE ticket_ai_analysis SET special_reason=%s WHERE id=%s", (REASONS[cid % len(REASONS)], aid))
    n += 1
print(f"23. ticket_ai_analysis 特别案例理由多样化: {n} 行")

conn.commit()
cur.close(); conn.close()
print("\n补充完成（幂等：重跑只补缺口，不重复插入）")
