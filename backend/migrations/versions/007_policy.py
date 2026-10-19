"""v6.11.23：政策资讯建表接库——新增 policy 表（留学政策资讯公开内容页数据源）

Revision ID: 007_policy
Revises: 006_schema_drift
Create Date: 2026-10-19

幂等：表存在则跳过；三类库安全（空库全链 001→007 / 历史迁移库续跑 / ORM 建库 stamp 后补齐）。
"""
from alembic import op
import sqlalchemy as sa

revision = "007_policy"
down_revision = "006_schema_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'policy'"
    )).scalar()
    if exists:
        return
    op.create_table(
        "policy",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("country", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("publish_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("create_time", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_country", "policy", ["country"])
    op.create_index("ix_policy_publish_date", "policy", ["publish_date"])
    op.create_index("ix_policy_status", "policy", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'policy'"
    )).scalar()
    if not exists:
        return
    op.drop_table("policy")
