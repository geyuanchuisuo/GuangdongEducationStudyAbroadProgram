"""initial: 27 tables

Revision ID: 001_initial
Revises:
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── M0: 公共/基础表 ──
    op.create_table(
        "sys_user",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("real_name", sa.String(50), nullable=False),
        sa.Column("user_type", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True, unique=True),
        sa.Column("employee_role", sa.String(50), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("permissions", sa.JSON, nullable=True),
        sa.Column("contact_info", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="正常"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sys_user_username", "sys_user", ["username"])
    op.create_index("ix_sys_user_user_type", "sys_user", ["user_type"])
    op.create_index("ix_sys_user_phone", "sys_user", ["phone"])
    op.create_index("ix_sys_user_department", "sys_user", ["department"])

    op.create_table(
        "sys_event",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("source_module", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sys_event_type", "sys_event", ["event_type"])
    op.create_index("ix_sys_event_source", "sys_event", ["source_module"])
    op.create_index("ix_sys_event_status", "sys_event", ["status"])

    op.create_table(
        "sys_approval",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("approval_type", sa.String(32), nullable=False),
        sa.Column("initiator_id", sa.BigInteger, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("approver_id", sa.BigInteger, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("target_id", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sys_approval_type", "sys_approval", ["approval_type"])
    op.create_index("ix_sys_approval_initiator", "sys_approval", ["initiator_id"])
    op.create_index("ix_sys_approval_approver", "sys_approval", ["approver_id"])
    op.create_index("ix_sys_approval_status", "sys_approval", ["status"])

    op.create_table(
        "sys_operation_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.BigInteger, nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sys_oplog_user", "sys_operation_log", ["user_id"])
    op.create_index("ix_sys_oplog_module", "sys_operation_log", ["module"])
    op.create_index("ix_sys_oplog_created", "sys_operation_log", ["created_at"])

    op.create_table(
        "sys_notification",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("0")),
        sa.Column("related_type", sa.String(32), nullable=True),
        sa.Column("related_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sys_notification_user", "sys_notification", ["user_id"])
    op.create_index("ix_sys_notification_type", "sys_notification", ["type"])

    # ── M1: 客户模块 ──
    op.create_table(
        "crm_lead",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("customer_name", sa.String(100), nullable=False),
        sa.Column("contact_info", sa.Text, nullable=True),
        sa.Column("background_info", sa.Text, nullable=True),
        sa.Column("follow_up_history", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), server_default="新录入"),
        sa.Column("owner_employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_crm_lead_status", "crm_lead", ["status"])
    op.create_index("ix_crm_lead_owner", "crm_lead", ["owner_employee_id"])

    op.create_table(
        "customer_assessment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("customer_name", sa.String(100), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=True),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("extracted_info", sa.JSON, nullable=True),
        sa.Column("assessment_result", sa.JSON, nullable=True),
        sa.Column("match_score", sa.Integer, nullable=True),
        sa.Column("matched_products", sa.JSON, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("is_valid", sa.Boolean, server_default=sa.text("1")),
        sa.Column("invalid_reason", sa.String(200), nullable=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_assessment_score", "customer_assessment", ["match_score"])
    op.create_index("ix_assessment_status", "customer_assessment", ["status"])
    op.create_index("ix_assessment_employee", "customer_assessment", ["employee_id"])

    op.create_table(
        "crm_follow_up",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("crm_lead.id"), nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("follow_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("next_action", sa.String(200), nullable=True),
        sa.Column("next_date", sa.DateTime, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_crm_followup_lead", "crm_follow_up", ["lead_id"])
    op.create_index("ix_crm_followup_employee", "crm_follow_up", ["employee_id"])

    # ── M2: 客服模块 ──
    op.create_table(
        "course_project",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("duration", sa.String(50), nullable=True),
        sa.Column("target_audience", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "event_lecture",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=True),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("end_time", sa.DateTime, nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("max_participants", sa.Integer, server_default=sa.text("0")),
        sa.Column("current_participants", sa.Integer, server_default=sa.text("0")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="报名中"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_event_type", "event_lecture", ["event_type"])
    op.create_index("ix_event_start", "event_lecture", ["start_time"])
    op.create_index("ix_event_status", "event_lecture", ["status"])

    op.create_table(
        "event_registration",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("event_lecture.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="已报名"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "user_id"),
    )
    op.create_index("ix_eventreg_event", "event_registration", ["event_id"])
    op.create_index("ix_eventreg_user", "event_registration", ["user_id"])

    op.create_table(
        "cs_chat_session",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("agent_type", sa.String(32), nullable=False, server_default="CUSTOMER"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cs_session_user", "cs_chat_session", ["user_id"])
    op.create_index("ix_cs_session_status", "cs_chat_session", ["status"])

    op.create_table(
        "cs_chat_message",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("cs_chat_session.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("card_data", sa.JSON, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cs_msg_session", "cs_chat_message", ["session_id"])

    op.create_table(
        "cs_intent_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("cs_chat_session.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("intent_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("converted", sa.Boolean, server_default=sa.text("0")),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("crm_lead.id"), nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cs_intent_session", "cs_intent_log", ["session_id"])
    op.create_index("ix_cs_intent_user", "cs_intent_log", ["user_id"])
    op.create_index("ix_cs_intent_type", "cs_intent_log", ["intent_type"])

    op.create_table(
        "cs_faq",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("keywords", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cs_faq_category", "cs_faq", ["category"])
    op.create_index("ix_cs_faq_status", "cs_faq", ["status"])

    # ── M3: 员工模块 ──
    op.create_table(
        "employee_org",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("employee_org.id"), nullable=True),
        sa.Column("org_type", sa.String(20), server_default="department"),
        sa.Column("leader_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_org_parent", "employee_org", ["parent_id"])
    op.create_index("ix_org_type", "employee_org", ["org_type"])
    op.create_index("ix_org_status", "employee_org", ["status"])

    op.create_table(
        "employee_daily_report",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "report_date"),
    )
    op.create_index("ix_daily_report_employee", "employee_daily_report", ["employee_id"])
    op.create_index("ix_daily_report_date", "employee_daily_report", ["report_date"])

    op.create_table(
        "employee_todo",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("todo_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("related_type", sa.String(50), nullable=True),
        sa.Column("related_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("priority", sa.String(10), server_default="medium"),
        sa.Column("due_time", sa.DateTime, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_todo_employee", "employee_todo", ["employee_id"])
    op.create_index("ix_todo_status", "employee_todo", ["status"])
    op.create_index("ix_todo_priority", "employee_todo", ["priority"])
    op.create_index("ix_todo_due", "employee_todo", ["due_time"])

    op.create_table(
        "student_score",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("course_name", sa.String(200), nullable=False),
        sa.Column("score", sa.Numeric(5, 1), nullable=True),
        sa.Column("exam_type", sa.String(50), nullable=True),
        sa.Column("exam_date", sa.Date, nullable=True),
        sa.Column("recorded_by", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )

    # ── M4: 学生模块 ──
    op.create_table(
        "student_admin_service",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("service_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("handler_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_psych_profile",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("assessment_date", sa.Date, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("profile_data", sa.JSON, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_psych_alert",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("handled_by", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("handle_note", sa.Text, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_feedback_ticket",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("handler_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_academic",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("course_project_id", sa.Integer, sa.ForeignKey("course_project.id"), nullable=True),
        sa.Column("enroll_date", sa.Date, nullable=True),
        sa.Column("progress_status", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "student_application_progress",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="in_progress"),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime, server_default=sa.func.now()),
    )

    # ── M5: 报告模块 ──
    op.create_table(
        "ai_report",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("report_title", sa.String(200), nullable=True),
        sa.Column("report_content", sa.JSON, nullable=True),
        sa.Column("time_range_start", sa.DateTime, nullable=True),
        sa.Column("time_range_end", sa.DateTime, nullable=True),
        sa.Column("generated_by", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="generating"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_report_type", "ai_report", ["report_type"])
    op.create_index("ix_report_range", "ai_report", ["time_range_start"])
    op.create_index("ix_report_status", "ai_report", ["status"])

    op.create_table(
        "ai_report_attachment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("ai_report.id"), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_report_attachment")
    op.drop_table("ai_report")
    op.drop_table("student_application_progress")
    op.drop_table("student_academic")
    op.drop_table("student_feedback_ticket")
    op.drop_table("student_psych_alert")
    op.drop_table("student_psych_profile")
    op.drop_table("student_admin_service")
    op.drop_table("student_score")
    op.drop_table("employee_todo")
    op.drop_table("employee_daily_report")
    op.drop_table("employee_org")
    op.drop_table("cs_faq")
    op.drop_table("cs_intent_log")
    op.drop_table("cs_chat_message")
    op.drop_table("cs_chat_session")
    op.drop_table("event_registration")
    op.drop_table("event_lecture")
    op.drop_table("course_project")
    op.drop_table("crm_follow_up")
    op.drop_table("customer_assessment")
    op.drop_table("crm_lead")
    op.drop_table("sys_notification")
    op.drop_table("sys_operation_log")
    op.drop_table("sys_approval")
    op.drop_table("sys_event")
    op.drop_table("sys_user")
