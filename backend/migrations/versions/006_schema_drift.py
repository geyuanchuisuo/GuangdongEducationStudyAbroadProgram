"""v6.11.13：迁移链漂移债清偿——对齐 ORM 结构（补 40 列 + 2 表 + 59 处类型/可空 + 死列放宽）

Revision ID: 006_schema_drift
Revises: 005_score_unique
Create Date: 2026-10-19

背景：历史迭代只在 ORM model 演进、靠 create_all 生效，迁移链（001~005）未同步，
导致「纯迁移链建库」与「ORM 建库」结构严重漂移，005 甚至因缺 semester 列直接失败。
本迁移把迁移链产物全面对齐 ORM 定义，全部幂等守护（已符合则跳过），三类库安全：
  a) 全新库 001→006 链式建库；b) 停在 004/005 的迁移库续跑；c) ORM 建库的开发/生产库 stamp 即可。

执行内容（按序）：
  0. 拆除引用「待加宽主键」的 FK（动态发现）→ 7 个主键 INT→BIGINT（保留 AUTO_INCREMENT）：
     crm_follow_up.id / crm_lead.id / cs_chat_message.id / cs_chat_session.id /
     cs_faq.id / cs_intent_log.id / customer_assessment.id
     → 51 处同名列类型/可空对齐（MODIFY，逐列幂等）
     → 2 个遗留死列 lead_id INT→BIGINT（crm_follow_up / cs_intent_log，为 FK 兼容加宽）
     → 5 个 NOT NULL 无默认值死列放宽为 NULL（否则迁移库上应用 INSERT 必失败：
       course_project.name / crm_lead.customer_name / student_admin_service.title /
       student_feedback_ticket.title / crm_follow_up.lead_id）
     → FK 原名挂回
  1. 补 40 列（12 表；student_score.semester 由 005 防御式补）
  2. 新列 FK ×3（approver_id / operator_id / teacher_id → sys_user.id）
  3. 存量列索引缺口 ×16（同列集无功能等价索引，沿用 ORM 命名）
  4. student_psych_profile.student_id 补 UNIQUE（先防御式去重）
  5. 补 2 张整表：cs_recommend_log（M2 推荐日志）、daily_report_annotation（M3 日报批示）

残留已知无害差异（不修，登记备查）：
  - 57 个 ORM 已删除的遗留死列保留（删列有数据丢失风险；5 个 NOT NULL 死列已放宽）；
  - 迁移链遗留死表 sys_approval（ORM 用 approval_instance/approval_task 替代）；
  - 历史索引/FK 命名差异（同列不同名，功能等价）；
  - customer.phone / sys_user.username / sys_user.phone 唯一性约束命名差异（功能等价）。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "006_schema_drift"
down_revision = "005_score_unique"
branch_labels = None
depends_on = None


def _colinfo(table: str, column: str):
    r = op.get_bind().execute(
        text(
            "SELECT COLUMN_TYPE, IS_NULLABLE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    )
    return r.fetchone()  # None 或 (type, 'YES'/'NO')


def _has_index(table: str, index: str) -> bool:
    r = op.get_bind().execute(
        text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
        ),
        {"t": table, "i": index},
    )
    return r.scalar() > 0


def _has_table(table: str) -> bool:
    r = op.get_bind().execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
        ),
        {"t": table},
    )
    return r.scalar() > 0


def _fks_referencing(table: str):
    """引用指定表的 FK 清单：(constraint_name, child_table, child_column)"""
    r = op.get_bind().execute(
        text(
            "SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = :t"
        ),
        {"t": table},
    )
    return r.fetchall()


# 7 个待加宽主键（INT→BIGINT AUTO_INCREMENT）
_PK_WIDEN = [
    "crm_follow_up", "crm_lead", "cs_chat_message", "cs_chat_session",
    "cs_faq", "cs_intent_log", "customer_assessment",
]

# 51 处类型/可空对齐：(table, column, orm_type, orm_nullable, mig_type, mig_nullable)
_ALTERS = [
    ("ai_report", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("ai_report_drill", "row_count", "int", "NO", "int", "YES"),
    ("approval_instance", "current_step", "int", "NO", "int", "YES"),
    ("approval_instance", "status", "varchar(16)", "NO", "varchar(16)", "YES"),
    ("approval_instance", "total_steps", "int", "NO", "int", "YES"),
    ("approval_task", "status", "varchar(16)", "NO", "varchar(16)", "YES"),
    ("course_project", "duration", "varchar(100)", "YES", "varchar(50)", "YES"),
    ("course_project", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("course_project", "target_audience", "text", "YES", "varchar(200)", "YES"),
    ("crm_follow_up", "content", "text", "YES", "text", "NO"),
    ("crm_follow_up", "customer_id", "bigint", "NO", "bigint", "YES"),
    ("crm_follow_up", "follow_type", "varchar(32)", "YES", "varchar(20)", "NO"),
    ("crm_follow_up", "next_action", "text", "YES", "varchar(200)", "YES"),
    ("crm_lead", "owner_employee_id", "int", "YES", "int", "NO"),
    ("crm_lead", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("cs_chat_message", "session_id", "bigint", "NO", "int", "NO"),
    ("cs_chat_session", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("cs_chat_session", "user_id", "int", "YES", "int", "NO"),
    ("cs_faq", "enabled", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("cs_faq", "sort_order", "int", "NO", "int", "YES"),
    ("cs_intent_log", "confidence", "double", "YES", "float", "YES"),
    ("cs_intent_log", "converted", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("cs_intent_log", "session_id", "bigint", "NO", "int", "NO"),
    ("cs_intent_log", "user_id", "int", "YES", "int", "NO"),
    ("customer", "auto_churned", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("customer", "phone_status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("customer", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("customer_assessment", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("employee_org", "org_type", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("employee_org", "sort_order", "int", "NO", "int", "YES"),
    ("employee_org", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("employee_todo", "priority", "varchar(10)", "NO", "varchar(10)", "YES"),
    ("employee_todo", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("event_lecture", "current_participants", "int", "NO", "int", "YES"),
    ("event_lecture", "max_participants", "int", "NO", "int", "YES"),
    ("event_lecture", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("event_registration", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("pending_lead", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("student_admin_service", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("student_application_progress", "status", "varchar(50)", "NO", "varchar(20)", "YES"),
    ("student_feedback_ticket", "content", "varchar(500)", "NO", "text", "NO"),
    ("student_feedback_ticket", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("student_psych_alert", "risk_level", "varchar(10)", "NO", "varchar(20)", "NO"),
    ("student_psych_alert", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("student_score", "course_name", "varchar(100)", "NO", "varchar(200)", "NO"),
    ("student_score", "score", "decimal(5,2)", "NO", "decimal(5,1)", "YES"),
    ("sys_event", "status", "varchar(16)", "NO", "varchar(16)", "YES"),
    ("sys_notification", "is_read", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("sys_user", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
    ("ticket_ai_analysis", "high_risk", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("ticket_ai_analysis", "low_satisfaction_candidate", "tinyint(1)", "NO", "tinyint(1)", "YES"),
    ("ticket_ai_analysis", "status", "varchar(20)", "NO", "varchar(20)", "YES"),
]

# 遗留死列 lead_id 加宽 + 放宽（ORM 已删此列，保留仅为不毁数据）
_LEGACY_LEAD_ID = [("crm_follow_up", "int", "NO"), ("cs_intent_log", "int", "YES")]

# NOT NULL 无默认值死列放宽为 NULL（不修则迁移库上应用 INSERT 必失败）
_DEAD_COL_RELAX = [
    ("course_project", "name", "varchar(200)"),
    ("crm_lead", "customer_name", "varchar(100)"),
    ("student_admin_service", "title", "varchar(200)"),
    ("student_feedback_ticket", "title", "varchar(200)"),
]

# (table, column, 加列后需补的索引名或 None) —— 40 列
_COLUMNS = [
    ("course_project", sa.Column("project_name", sa.String(200), nullable=False), None),
    ("course_project", sa.Column("tuition_fee", sa.Numeric(10, 2), nullable=True), None),
    ("crm_follow_up", sa.Column("created_at", sa.DateTime, nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")), None),
    ("customer", sa.Column("economy", sa.String(100), nullable=True, comment="家庭经济状况"), None),
    ("customer", sa.Column("needs", sa.String(200), nullable=True, comment="职业/教育需求"), None),
    ("customer", sa.Column("study_intent", sa.String(200), nullable=True, comment="留学意愿及意向国家"), None),
    ("customer", sa.Column("german_ability", sa.String(100), nullable=True, comment="德语能力"), None),
    ("customer", sa.Column("english_ability", sa.String(100), nullable=True, comment="英语能力"), None),
    ("customer", sa.Column("closed_training", sa.String(100), nullable=True, comment="是否接受封闭式实训"), None),
    ("customer", sa.Column("criminal_record", sa.String(100), nullable=True, comment="有无犯罪记录"), None),
    ("customer", sa.Column("belt_and_road", sa.String(200), nullable=True, comment="一带一路/政策认知"), None),
    ("customer_assessment", sa.Column("score", sa.Integer, nullable=True, comment="匹配度评分(90/70/50/20)"), "ix_customer_assessment_score"),
    ("customer_assessment", sa.Column("created_at", sa.DateTime, nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")), None),
    ("employee_daily_report", sa.Column("status", sa.String(20), nullable=False, comment="draft/submitted/late_pending"), "ix_employee_daily_report_status"),
    ("employee_daily_report", sa.Column("is_late", sa.Boolean, nullable=False, comment="是否迟报（次日0点后提交或补报通过）"), None),
    ("student_academic", sa.Column("item_type", sa.String(50), nullable=False), "ix_student_academic_item_type"),
    ("student_academic", sa.Column("title", sa.String(200), nullable=False), None),
    ("student_academic", sa.Column("description", sa.Text, nullable=True), None),
    ("student_academic", sa.Column("course_name", sa.String(100), nullable=True), None),
    ("student_academic", sa.Column("due_time", sa.DateTime, nullable=False), "ix_student_academic_due_time"),
    ("student_academic", sa.Column("reminder_sent", sa.Boolean, nullable=False), None),
    ("student_academic", sa.Column("reminder_time", sa.DateTime, nullable=True), None),
    ("student_admin_service", sa.Column("start_time", sa.DateTime, nullable=True), None),
    ("student_admin_service", sa.Column("end_time", sa.DateTime, nullable=True), None),
    ("student_admin_service", sa.Column("reason", sa.Text, nullable=True), None),
    ("student_admin_service", sa.Column("approver_id", sa.Integer, nullable=True), None),  # FK 见下
    ("student_admin_service", sa.Column("related_academic_id", sa.Integer, nullable=True), None),
    ("student_application_progress", sa.Column("notes", sa.Text, nullable=True), None),
    ("student_application_progress", sa.Column("operator_id", sa.Integer, nullable=True), None),  # FK 见下
    ("student_feedback_ticket", sa.Column("detail", sa.Text, nullable=True), None),
    ("student_feedback_ticket", sa.Column("solution", sa.Text, nullable=True), None),
    ("student_feedback_ticket", sa.Column("is_notified", sa.Boolean, nullable=False), None),
    ("student_psych_alert", sa.Column("trigger_reason", sa.Text, nullable=False), None),
    ("student_psych_alert", sa.Column("teacher_id", sa.Integer, nullable=True), None),  # FK 见下
    ("student_psych_alert", sa.Column("handled_action", sa.String(20), nullable=True, comment="处理动作：communicated/referred/resolved"), None),
    ("student_psych_alert", sa.Column("handled_at", sa.DateTime, nullable=True, comment="处理时间"), None),
    ("student_psych_profile", sa.Column("latest_emotion_tag", sa.String(50), nullable=True), "ix_student_psych_profile_latest_emotion_tag"),
    ("student_psych_profile", sa.Column("emotion_score", sa.Integer, nullable=True), None),
    ("student_psych_profile", sa.Column("last_interaction_time", sa.DateTime, nullable=True), None),
    ("student_psych_profile", sa.Column("emotion_history", sa.JSON, nullable=True), None),
]

# 新列上的外键（MySQL 自动建同名索引，与 ORM 库一致）
_FKS = [
    ("student_admin_service", "approver_id", "sys_user", "id"),
    ("student_application_progress", "operator_id", "sys_user", "id"),
    ("student_psych_alert", "teacher_id", "sys_user", "id"),
]

# 存量列上无功能等价索引的缺口（ORM 命名）
_INDEXES = [
    ("course_project", "ix_course_project_category", ["category"]),
    ("course_project", "ix_course_project_status", ["status"]),
    ("student_admin_service", "ix_student_admin_service_service_type", ["service_type"]),
    ("student_admin_service", "ix_student_admin_service_status", ["status"]),
    ("student_application_progress", "ix_student_application_progress_stage", ["stage"]),
    ("student_application_progress", "ix_student_application_progress_update_time", ["update_time"]),
    ("student_feedback_ticket", "ix_student_feedback_ticket_status", ["status"]),
    ("student_psych_alert", "ix_student_psych_alert_risk_level", ["risk_level"]),
    ("student_psych_alert", "ix_student_psych_alert_status", ["status"]),
    ("student_score", "ix_student_score_course_name", ["course_name"]),
    ("student_score", "ix_student_score_semester", ["semester"]),
    ("student_score", "ix_student_score_student_id", ["student_id"]),
]


def _drop_index_fk_safe(table: str, index: str, cols: list) -> None:
    """删索引；若被本表 FK 依赖（MySQL 1553），先拆 FK、删索引，再原名挂回 FK。"""
    if not _has_index(table, index):
        return
    bind = op.get_bind()
    fks = bind.execute(
        text(
            "SELECT DISTINCT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND REFERENCED_TABLE_NAME IS NOT NULL"
        ),
        {"t": table},
    ).fetchall()
    dep = [f for f in fks if f[1] in cols]
    for name, _c, _rt, _rc in dep:
        op.drop_constraint(name, table, type_="foreignkey")
    op.drop_index(index, table)
    for name, c, rt, rc in dep:
        op.create_foreign_key(name, table, rt, [c], [rc])


def _modify(table: str, column: str, type_str: str, nullable: str) -> None:
    """幂等 MODIFY：当前定义已与目标一致则跳过。"""
    info = _colinfo(table, column)
    if info is None or (info[0] == type_str and info[1] == nullable):
        return
    nn = "NULL" if nullable == "YES" else "NOT NULL"
    op.execute(f"ALTER TABLE {table} MODIFY {column} {type_str} {nn}")


def upgrade() -> None:
    # ── 0a. 拆除引用待加宽主键的 FK（记录原名以便挂回）
    dropped = []
    for pt in _PK_WIDEN:
        for name, ct, cc in _fks_referencing(pt):
            op.drop_constraint(name, ct, type_="foreignkey")
            dropped.append((name, ct, cc, pt))

    # ── 0b. 7 个主键 INT→BIGINT（保留 AUTO_INCREMENT）
    for pt in _PK_WIDEN:
        info = _colinfo(pt, "id")
        if info and info[0] != "bigint":
            op.execute(f"ALTER TABLE {pt} MODIFY id BIGINT NOT NULL AUTO_INCREMENT")

    # ── 0c. 51 处类型/可空对齐（含 FK 子列 session_id 加宽）
    for table, col, new_t, new_n, _old_t, _old_n in _ALTERS:
        _modify(table, col, new_t, new_n)

    # ── 0d. 遗留死列 lead_id 加宽（FK 兼容）
    for t, _old_t, _old_n in _LEGACY_LEAD_ID:
        _modify(t, "lead_id", "bigint", "YES")

    # ── 0e. NOT NULL 无默认值死列放宽为 NULL
    for t, c, ct in _DEAD_COL_RELAX:
        _modify(t, c, ct, "YES")

    # ── 0f. FK 原名挂回
    for name, ct, cc, pt in dropped:
        op.create_foreign_key(name, ct, pt, [cc], ["id"])

    # ── 1. 补 40 列（幂等）
    for table, col, ix in _COLUMNS:
        if _colinfo(table, col.name) is None:
            op.add_column(table, col)
        if ix and not _has_index(table, ix):
            op.create_index(ix, table, [col.name])

    # ── 2. 新列上的外键（幂等：以 MySQL 自动索引同名探测）
    for table, col, rt, rc in _FKS:
        if not _has_index(table, col):
            op.create_foreign_key(None, table, rt, [col], [rc])

    # ── 3. 存量列索引缺口（幂等）
    for table, ix, cols in _INDEXES:
        if not _has_index(table, ix):
            op.create_index(ix, table, cols)

    # ── 4. student_psych_profile.student_id 补 UNIQUE（先防御式去重，保留最小 id）
    if not _has_index("student_psych_profile", "ix_student_psych_profile_student_id"):
        op.execute(
            """
            DELETE p FROM student_psych_profile p
            JOIN student_psych_profile p2
              ON p.student_id = p2.student_id AND p.id > p2.id
            """
        )
        op.create_unique_constraint("ix_student_psych_profile_student_id", "student_psych_profile", ["student_id"])

    # ── 5. 补 2 张整表（幂等）
    if not _has_table("cs_recommend_log"):
        op.create_table(
            "cs_recommend_log",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.BigInteger, sa.ForeignKey("cs_chat_session.id"), nullable=False),
            sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户"),
            sa.Column("course_id", sa.Integer, sa.ForeignKey("course_project.id"), nullable=True, comment="推荐课程ID"),
            sa.Column("event_id", sa.Integer, sa.ForeignKey("event_lecture.id"), nullable=True, comment="推荐活动ID"),
            sa.Column("recommendation_type", sa.String(32), nullable=True, comment="推荐类型(course/event/other)"),
            sa.Column("item_name", sa.String(200), nullable=True, comment="推荐项名称"),
            sa.Column("created_at", sa.DateTime, nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_cs_recommend_log_session_id", "cs_recommend_log", ["session_id"])
        op.create_index("ix_cs_recommend_log_customer_id", "cs_recommend_log", ["customer_id"])
        op.create_index("ix_cs_recommend_log_recommendation_type", "cs_recommend_log", ["recommendation_type"])

    if not _has_table("daily_report_annotation"):
        op.create_table(
            "daily_report_annotation",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("report_id", sa.Integer, sa.ForeignKey("employee_daily_report.id"), nullable=False),
            sa.Column("manager_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("create_time", sa.DateTime, nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_daily_report_annotation_report_id", "daily_report_annotation", ["report_id"])
        op.create_index("ix_daily_report_annotation_manager_id", "daily_report_annotation", ["manager_id"])


def downgrade() -> None:
    # 5. 删 2 表
    if _has_table("daily_report_annotation"):
        op.drop_table("daily_report_annotation")
    if _has_table("cs_recommend_log"):
        op.drop_table("cs_recommend_log")
    # 4. 撤 UNIQUE（该索引被 student_psych_profile.student_id 的 FK 依赖，走安全删除）
    _drop_index_fk_safe("student_psych_profile", "ix_student_psych_profile_student_id", ["student_id"])
    # 3. 撤存量索引（student_score.student_id 等可能被 FK 依赖，走安全删除）
    for table, ix, cols in reversed(_INDEXES):
        _drop_index_fk_safe(table, ix, cols)
    # 2. 撤新列 FK
    for table, col, _rt, _rc in reversed(_FKS):
        if _has_index(table, col):
            # 动态查名删除
            r = op.get_bind().execute(
                text(
                    "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c "
                    "AND REFERENCED_TABLE_NAME IS NOT NULL"
                ),
                {"t": table, "c": col},
            )
            row = r.fetchone()
            if row:
                op.drop_constraint(row[0], table, type_="foreignkey")
    # 1. 撤 40 列
    for table, col, ix in reversed(_COLUMNS):
        if ix and _has_index(table, ix):
            op.drop_index(ix, table)
        if _colinfo(table, col.name) is not None:
            op.drop_column(table, col.name)
    # 0f. 拆 FK（同 upgrade 的动态发现）
    dropped = []
    for pt in _PK_WIDEN:
        for name, ct, cc in _fks_referencing(pt):
            op.drop_constraint(name, ct, type_="foreignkey")
            dropped.append((name, ct, cc, pt))
    # 0e/0d/0c/0b 逆序还原
    for t, c, ct in reversed(_DEAD_COL_RELAX):
        _modify(t, c, ct, "NO")
    for t, old_t, old_n in reversed(_LEGACY_LEAD_ID):
        _modify(t, "lead_id", old_t, old_n)
    for table, col, _new_t, _new_n, old_t, old_n in reversed(_ALTERS):
        _modify(table, col, old_t, old_n)
    for pt in reversed(_PK_WIDEN):
        info = _colinfo(pt, "id")
        if info and info[0] != "int":
            op.execute(f"ALTER TABLE {pt} MODIFY id INT NOT NULL AUTO_INCREMENT")
    for name, ct, cc, pt in dropped:
        op.create_foreign_key(name, ct, pt, [cc], ["id"])
