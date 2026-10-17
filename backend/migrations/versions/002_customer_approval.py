"""v2: customer master + dual approval tables

Revision ID: 002_customer_approval
Revises: 001_initial
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_customer_approval"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 新增：客户主表 ──
    op.create_table(
        "customer",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(20), nullable=True, unique=True, comment="手机号(业务唯一键)"),
        sa.Column("wechat", sa.String(100), nullable=True, comment="微信号"),
        sa.Column("name", sa.String(100), nullable=True, comment="姓名"),
        sa.Column("gender", sa.String(10), nullable=True, comment="性别"),
        sa.Column("age", sa.Integer, nullable=True, comment="年龄"),
        sa.Column("education", sa.String(50), nullable=True, comment="学历"),
        sa.Column("source_channel", sa.String(32), nullable=True, comment="来源渠道"),
        sa.Column("owner_employee_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True, comment="负责员工"),
        sa.Column("status", sa.String(20), server_default="NEW", comment="客户状态(6态)"),
        sa.Column("phone_status", sa.String(20), server_default="normal", comment="手机号状态"),
        sa.Column("first_register_at", sa.DateTime, nullable=True, comment="首次注册时间"),
        sa.Column("first_submit_at", sa.DateTime, nullable=True, comment="首次员工提交时间"),
        sa.Column("last_login_at", sa.DateTime, nullable=True, comment="最后登录时间"),
        sa.Column("auto_churned", sa.Boolean, server_default=sa.text("0"), comment="系统自动流失标记"),
        sa.Column("churned_at", sa.DateTime, nullable=True, comment="流失时间"),
        sa.Column("reflowed_at", sa.DateTime, nullable=True, comment="回流时间"),
        sa.Column("sys_user_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=True, comment="关联账号ID"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_customer_phone", "customer", ["phone"])
    op.create_index("ix_customer_status", "customer", ["status"])
    op.create_index("ix_customer_source", "customer", ["source_channel"])
    op.create_index("ix_customer_owner", "customer", ["owner_employee_id"])

    # ── 新增：待补全线索表 ──
    op.create_table(
        "pending_lead",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("wechat", sa.String(100), nullable=True, comment="微信号"),
        sa.Column("name", sa.String(100), nullable=True, comment="姓名"),
        sa.Column("raw_info", sa.Text, nullable=True, comment="原始信息"),
        sa.Column("source_session_id", sa.BigInteger, nullable=True, comment="来源会话ID"),
        sa.Column("merged_customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="合并后的客户ID"),
        sa.Column("status", sa.String(20), server_default="pending", comment="状态"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── 新增：审批实例表 ──
    op.create_table(
        "approval_instance",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("biz_type", sa.String(32), nullable=False, comment="业务类型"),
        sa.Column("biz_id", sa.BigInteger, nullable=True, comment="关联业务ID"),
        sa.Column("title", sa.String(200), nullable=True, comment="审批标题"),
        sa.Column("initiator_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False, comment="发起人"),
        sa.Column("status", sa.String(16), server_default="pending", comment="状态"),
        sa.Column("current_step", sa.Integer, server_default=sa.text("1"), comment="当前步骤"),
        sa.Column("total_steps", sa.Integer, server_default=sa.text("1"), comment="总步骤数"),
        sa.Column("finished_at", sa.DateTime, nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_inst_type", "approval_instance", ["biz_type"])
    op.create_index("ix_approval_inst_initiator", "approval_instance", ["initiator_id"])
    op.create_index("ix_approval_inst_status", "approval_instance", ["status"])

    # ── 新增：审批任务表 ──
    op.create_table(
        "approval_task",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.BigInteger, sa.ForeignKey("approval_instance.id"), nullable=False, comment="审批实例ID"),
        sa.Column("approver_id", sa.Integer, sa.ForeignKey("sys_user.id"), nullable=False, comment="审批人"),
        sa.Column("seq_no", sa.Integer, nullable=False, comment="审批顺序"),
        sa.Column("action", sa.String(16), nullable=True, comment="审批动作"),
        sa.Column("comment", sa.Text, nullable=True, comment="审批意见"),
        sa.Column("acted_at", sa.DateTime, nullable=True, comment="操作时间"),
        sa.Column("status", sa.String(16), server_default="pending", comment="任务状态"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_task_instance", "approval_task", ["instance_id"])
    op.create_index("ix_approval_task_approver", "approval_task", ["approver_id"])
    op.create_index("ix_approval_task_status", "approval_task", ["status"])

    # ── 修改：crm_lead 改为线索表 ──
    op.add_column("crm_lead", sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户ID"))
    op.add_column("crm_lead", sa.Column("source", sa.String(32), nullable=True, comment="线索来源"))
    op.add_column("crm_lead", sa.Column("raw_input", sa.Text, nullable=True, comment="原始录入信息"))
    op.add_column("crm_lead", sa.Column("created_at", sa.DateTime, server_default=sa.func.now()))
    op.add_column("crm_lead", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))
    op.create_index("ix_crm_lead_customer", "crm_lead", ["customer_id"])

    # ── 修改：customer_assessment 加 customer_id ──
    op.add_column("customer_assessment", sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户ID"))
    op.add_column("customer_assessment", sa.Column("batch_no", sa.String(64), nullable=True, comment="批次号"))
    op.add_column("customer_assessment", sa.Column("input_source", sa.String(32), nullable=True, comment="输入来源"))
    op.add_column("customer_assessment", sa.Column("sg_conclusion", sa.String(20), nullable=True, comment="新加坡结论"))
    op.add_column("customer_assessment", sa.Column("de_conclusion", sa.String(20), nullable=True, comment="德国结论"))
    op.add_column("customer_assessment", sa.Column("dimensions_json", sa.JSON, nullable=True, comment="逐维度证据"))
    op.add_column("customer_assessment", sa.Column("matched_programs_json", sa.JSON, nullable=True))
    op.add_column("customer_assessment", sa.Column("recommended_json", sa.JSON, nullable=True))
    op.add_column("customer_assessment", sa.Column("missing_info_json", sa.JSON, nullable=True))
    op.add_column("customer_assessment", sa.Column("conflicts_json", sa.JSON, nullable=True))
    op.add_column("customer_assessment", sa.Column("overview", sa.Text, nullable=True, comment="客户速览"))
    op.add_column("customer_assessment", sa.Column("follow_up_advice", sa.Text, nullable=True, comment="跟进建议"))
    op.add_column("customer_assessment", sa.Column("prompt_version", sa.String(20), nullable=True))
    op.add_column("customer_assessment", sa.Column("dify_run_id", sa.String(64), nullable=True))
    op.create_index("ix_assessment_customer", "customer_assessment", ["customer_id"])

    # ── 修改：crm_follow_up 改为引用 customer ──
    op.add_column("crm_follow_up", sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户ID"))
    op.create_index("ix_crm_followup_customer", "crm_follow_up", ["customer_id"])

    # ── 修改：cs_chat_session 加 customer_id ──
    op.add_column("cs_chat_session", sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户"))
    op.add_column("cs_chat_session", sa.Column("intent_summary", sa.Text, nullable=True))
    op.add_column("cs_chat_session", sa.Column("tags_json", sa.JSON, nullable=True))
    op.add_column("cs_chat_session", sa.Column("dify_conversation_id", sa.String(64), nullable=True))
    op.add_column("cs_chat_session", sa.Column("created_at", sa.DateTime, server_default=sa.func.now()))
    op.add_column("cs_chat_session", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))
    op.create_index("ix_cs_session_customer", "cs_chat_session", ["customer_id"])

    # ── 修改：cs_chat_message 增加字段 ──
    op.add_column("cs_chat_message", sa.Column("intent", sa.String(64), nullable=True, comment="命中意图"))
    op.add_column("cs_chat_message", sa.Column("slots_json", sa.JSON, nullable=True))
    op.add_column("cs_chat_message", sa.Column("citations_json", sa.JSON, nullable=True))
    op.add_column("cs_chat_message", sa.Column("tokens", sa.Integer, nullable=True))
    op.add_column("cs_chat_message", sa.Column("created_at", sa.DateTime, server_default=sa.func.now()))

    # ── 修改：cs_intent_log 改为引用 customer ──
    op.add_column("cs_intent_log", sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("customer.id"), nullable=True, comment="关联客户"))
    op.add_column("cs_intent_log", sa.Column("created_at", sa.DateTime, server_default=sa.func.now()))
    op.create_index("ix_cs_intent_customer", "cs_intent_log", ["customer_id"])

    # ── 修改：cs_faq 字段调整 ──
    op.add_column("cs_faq", sa.Column("enabled", sa.Boolean, server_default=sa.text("1"), comment="是否启用"))
    op.add_column("cs_faq", sa.Column("created_at", sa.DateTime, server_default=sa.func.now()))
    op.add_column("cs_faq", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))


def _drop_column_fks(bind, table: str, column: str) -> None:
    """删除 table.column 上的全部外键（FK 名为 MySQL 自动生成，需运行时探测）。"""
    insp = sa.inspect(bind)
    for fk in insp.get_foreign_keys(table):
        if column in fk["constrained_columns"]:
            op.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {fk['name']}")


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("cs_faq", "updated_at")
    op.drop_column("cs_faq", "created_at")
    op.drop_column("cs_faq", "enabled")
    # 注意：customer_id 各列的 FK 与单列索引必须先删 FK 再删列——
    # MySQL 禁止删除 FK 依赖的索引（errno 1553）与 FK 依赖的列（errno 1828），
    # drop_column 不会连带删 FK；索引在列删除时随列消失。
    _drop_column_fks(bind, "cs_intent_log", "customer_id")
    op.drop_column("cs_intent_log", "created_at")
    op.drop_column("cs_intent_log", "customer_id")
    op.drop_column("cs_chat_message", "created_at")
    op.drop_column("cs_chat_message", "tokens")
    op.drop_column("cs_chat_message", "citations_json")
    op.drop_column("cs_chat_message", "slots_json")
    op.drop_column("cs_chat_message", "intent")
    _drop_column_fks(bind, "cs_chat_session", "customer_id")
    op.drop_column("cs_chat_session", "updated_at")
    op.drop_column("cs_chat_session", "created_at")
    op.drop_column("cs_chat_session", "dify_conversation_id")
    op.drop_column("cs_chat_session", "tags_json")
    op.drop_column("cs_chat_session", "intent_summary")
    op.drop_column("cs_chat_session", "customer_id")
    _drop_column_fks(bind, "crm_follow_up", "customer_id")
    op.drop_column("crm_follow_up", "customer_id")
    _drop_column_fks(bind, "customer_assessment", "customer_id")
    op.drop_column("customer_assessment", "dify_run_id")
    op.drop_column("customer_assessment", "prompt_version")
    op.drop_column("customer_assessment", "follow_up_advice")
    op.drop_column("customer_assessment", "overview")
    op.drop_column("customer_assessment", "conflicts_json")
    op.drop_column("customer_assessment", "missing_info_json")
    op.drop_column("customer_assessment", "recommended_json")
    op.drop_column("customer_assessment", "matched_programs_json")
    op.drop_column("customer_assessment", "dimensions_json")
    op.drop_column("customer_assessment", "de_conclusion")
    op.drop_column("customer_assessment", "sg_conclusion")
    op.drop_column("customer_assessment", "input_source")
    op.drop_column("customer_assessment", "batch_no")
    op.drop_column("customer_assessment", "customer_id")
    _drop_column_fks(bind, "crm_lead", "customer_id")
    op.drop_column("crm_lead", "updated_at")
    op.drop_column("crm_lead", "created_at")
    op.drop_column("crm_lead", "raw_input")
    op.drop_column("crm_lead", "source")
    op.drop_column("crm_lead", "customer_id")
    op.drop_table("approval_task")
    op.drop_table("approval_instance")
    op.drop_table("pending_lead")
    op.drop_table("customer")
