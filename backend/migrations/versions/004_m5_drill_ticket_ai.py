"""v6.11.0：M5 下钻快照表 + 投诉工单 AI 分析表

Revision ID: 004_m5_drill_ticket_ai
Revises: 003_report_columns
Create Date: 2026-10-18

依据：M5 一期需求确认（2026-10-18）§2.2 快照、§2.6 投诉 AI 分析。
只新增 M5 自己的两张表，不改动 M1–M4 任何表结构与数据。
"""
from alembic import op
import sqlalchemy as sa

revision = "004_m5_drill_ticket_ai"
down_revision = "003_report_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_report_drill",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("drill_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        # 显式命名外键：MySQL 下降级必须先摘 FK 才能删其索引（errno 1553）
        sa.ForeignKeyConstraint(
            ["report_id"], ["ai_report.id"], name="fk_ai_report_drill_report"
        ),
    )
    op.create_index("ix_ai_report_drill_report_id", "ai_report_drill", ["report_id"])
    op.create_index("ix_ai_report_drill_drill_type", "ai_report_drill", ["drill_type"])

    op.create_table(
        "ticket_ai_analysis",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("low_satisfaction_candidate", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("high_risk", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("special_reason", sa.Text(), nullable=True),
        sa.Column("model_source", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ticket_ai_analysis_ticket_id", "ticket_ai_analysis", ["ticket_id"])
    op.create_index("ix_ticket_ai_analysis_status", "ticket_ai_analysis", ["status"])


def downgrade() -> None:
    # 先摘索引再删表，避免 MySQL 索引引用导致的降级失败
    op.drop_index("ix_ticket_ai_analysis_status", table_name="ticket_ai_analysis")
    op.drop_index("ix_ticket_ai_analysis_ticket_id", table_name="ticket_ai_analysis")
    op.drop_table("ticket_ai_analysis")

    # MySQL 下必须先删外键，才能删掉该外键依赖的索引（errno 1553）
    op.drop_constraint("fk_ai_report_drill_report", "ai_report_drill", type_="foreignkey")
    op.drop_index("ix_ai_report_drill_drill_type", table_name="ai_report_drill")
    op.drop_index("ix_ai_report_drill_report_id", table_name="ai_report_drill")
    op.drop_table("ai_report_drill")
