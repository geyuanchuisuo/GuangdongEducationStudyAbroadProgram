"""v3: ai_report / ai_report_attachment 与 ORM 对齐（v6.8.5 三列 + 字段漂移修复）

Revision ID: 003_report_columns
Revises: 002_customer_approval
Create Date: 2026-10-17

对齐目标：空库 `alembic upgrade head` 建出的两张报告表与 app/models/crm.py 的 ORM 一致。
001_initial.py 建表后 M5 演进产生的漂移（审计 M5-13.3）：
  1. ai_report 缺 v6.8.5 新增的三列：version / data_source_status / error_message
  2. 两表时间列名漂移：001 为 create_time，ORM 为 created_at
  3. ai_report_attachment.file_type 长度漂移：001 String(20)，ORM String(32)
  4. 主键/外键类型漂移：001 为 INT，anhoa v6.8.0 起 ORM 统一 BigInt with_variant
     （MySQL 侧为 BIGINT；SQLite 侧 INTEGER，迁移只面向 MySQL）

所有步骤先查 information_schema / 外键实际名再执行，可重复执行（幂等）。
约定偏差说明：version / data_source_status 补列时带 server_default（"1" / "mock"），
为存量行兜底；ORM 侧为客户端 default，无 server_default，属有意差异（不影响类型/可空性一致）。

⚠️ 验收状态（2026-10-17）：本迁移代码已完成，但端到端验收（空库 alembic upgrade head）
被上游缺陷阻塞——002_customer_approval 的 4 处 FK 列为 BigInteger→sys_user.id(INT)，
MySQL errno 150，迁移链无法到 head（详见运行日志 LOG-033）。待上游修复 002 后
重拉 master 完成验收：空库 upgrade head + 与 ORM 逐列比对 + downgrade/upgrade 幂等回环。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_report_columns"
down_revision: Union[str, None] = "002_customer_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_meta(bind, table: str) -> dict:
    """{列名: {"type": DATA_TYPE, "len": CHARACTER_MAXIMUM_LENGTH}}"""
    rows = bind.execute(sa.text(
        "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
    ), {"t": table}).mappings()
    return {r["COLUMN_NAME"]: {"type": r["DATA_TYPE"], "len": r["CHARACTER_MAXIMUM_LENGTH"]} for r in rows}


def _fk_names(bind, table: str, column: str) -> list[str]:
    insp = sa.inspect(bind)
    return [fk["name"] for fk in insp.get_foreign_keys(table) if column in fk["constrained_columns"]]


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. ai_report 补 v6.8.5 三列 ──
    cols = _col_meta(bind, "ai_report")
    if cols and "version" not in cols:
        op.add_column("ai_report", sa.Column("version", sa.Integer, nullable=False, server_default="1",
                                             comment="版本号（同类型同周期递增）"))
    if cols and "data_source_status" not in cols:
        op.add_column("ai_report", sa.Column("data_source_status", sa.String(20), nullable=False,
                                             server_default="mock", comment="数据来源状态(mock/production)"))
    if cols and "error_message" not in cols:
        op.add_column("ai_report", sa.Column("error_message", sa.Text, nullable=True, comment="生成失败原因"))

    # ── 2. 时间列名对齐：create_time → created_at ──
    for table in ("ai_report", "ai_report_attachment"):
        cols = _col_meta(bind, table)
        if cols and "create_time" in cols and "created_at" not in cols:
            op.execute(f"ALTER TABLE {table} RENAME COLUMN create_time TO created_at")

    # ── 3. file_type 长度对齐：String(20) → String(32) ──
    cols = _col_meta(bind, "ai_report_attachment")
    if cols and "file_type" in cols and cols["file_type"]["len"] not in (32, None):
        op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN file_type VARCHAR(32) NULL")

    # ── 4. 主键/外键 INT → BIGINT（先摘子表外键，改完回挂） ──
    ai_cols = _col_meta(bind, "ai_report")
    att_cols = _col_meta(bind, "ai_report_attachment")
    need_parent = ai_cols and ai_cols["id"]["type"] == "int"
    need_child = att_cols and (att_cols["id"]["type"] == "int" or att_cols["report_id"]["type"] == "int")
    if need_child or need_parent:
        fk_names = _fk_names(bind, "ai_report_attachment", "report_id")
        for name in fk_names:
            op.execute(f"ALTER TABLE ai_report_attachment DROP FOREIGN KEY {name}")
        if need_child:
            op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN id BIGINT AUTO_INCREMENT")
            op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN report_id BIGINT NOT NULL")
        if need_parent:
            op.execute("ALTER TABLE ai_report MODIFY COLUMN id BIGINT AUTO_INCREMENT")
        for name in fk_names:
            op.execute(
                "ALTER TABLE ai_report_attachment ADD CONSTRAINT "
                f"{name} FOREIGN KEY (report_id) REFERENCES ai_report (id)"
            )


def downgrade() -> None:
    """回滚到 001+002 形态（BIGINT→INT、还原列名/长度、删三列）。"""
    bind = op.get_bind()

    ai_cols = _col_meta(bind, "ai_report")
    att_cols = _col_meta(bind, "ai_report_attachment")
    if ai_cols and ai_cols["id"]["type"] == "bigint":
        fk_names = _fk_names(bind, "ai_report_attachment", "report_id")
        for name in fk_names:
            op.execute(f"ALTER TABLE ai_report_attachment DROP FOREIGN KEY {name}")
        if att_cols:
            op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN id INT AUTO_INCREMENT")
            op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN report_id INT NOT NULL")
        op.execute("ALTER TABLE ai_report MODIFY COLUMN id INT AUTO_INCREMENT")
        for name in fk_names:
            op.execute(
                "ALTER TABLE ai_report_attachment ADD CONSTRAINT "
                f"{name} FOREIGN KEY (report_id) REFERENCES ai_report (id)"
            )

    cols = _col_meta(bind, "ai_report_attachment")
    if cols and "file_type" in cols and cols["file_type"]["len"] not in (20, None):
        op.execute("ALTER TABLE ai_report_attachment MODIFY COLUMN file_type VARCHAR(20) NULL")

    for table in ("ai_report", "ai_report_attachment"):
        cols = _col_meta(bind, table)
        if cols and "created_at" in cols and "create_time" not in cols:
            op.execute(f"ALTER TABLE {table} RENAME COLUMN created_at TO create_time")

    cols = _col_meta(bind, "ai_report")
    if cols and "error_message" in cols:
        op.drop_column("ai_report", "error_message")
    if cols and "data_source_status" in cols:
        op.drop_column("ai_report", "data_source_status")
    if cols and "version" in cols:
        op.drop_column("ai_report", "version")
