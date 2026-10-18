"""v6.11.3：M3 成绩唯一约束（student_id + course_name + semester）

Revision ID: 005_score_unique
Revises: 004_m5_drill_ticket_ai
Create Date: 2026-10-18

依据：《前端无法解决问题清单》P0#2 —— 成绩重复录入缺少服务端约束。
步骤：⓪防御式补列 semester（纯迁移链建库缺此列：ORM 演进未同步进迁移的漂移债，
     v6.11.13 修复；ORM 建库的库已有此列则跳过，幂等）
     ①存量 semester NULL 规范化为空串（MySQL 唯一索引对 NULL 不生效）
     ②清理存量重复数据（每组保留最小 id）
     ③添加唯一索引 uq_student_score_unique（已存在则跳过，幂等）
注意：downgrade 只回滚唯一约束；防御式补上的 semester 列不回滚（无法区分列来源，误删会毁数据）。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "005_score_unique"
down_revision = "004_m5_drill_ticket_ai"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    r = op.get_bind().execute(
        text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    )
    return r.scalar() > 0


def _has_index(table: str, index: str) -> bool:
    r = op.get_bind().execute(
        text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
        ),
        {"t": table, "i": index},
    )
    return r.scalar() > 0


def upgrade() -> None:
    # ⓪ 防御式补列：迁移链建的 student_score 无 semester 列则先补（对齐 ORM String(50) NULL）
    if not _has_column("student_score", "semester"):
        op.add_column("student_score", sa.Column("semester", sa.String(50), nullable=True))
    # ① semester NULL → ''（唯一索引需非 NULL 才能拦截重复）
    op.execute("UPDATE student_score SET semester = '' WHERE semester IS NULL")
    # ② 清理存量重复：同 (student_id, course_name, semester) 仅保留最小 id
    op.execute(
        """
        DELETE s FROM student_score s
        JOIN student_score s2
          ON s.student_id = s2.student_id
         AND s.course_name = s2.course_name
         AND s.semester = s2.semester
         AND s.id > s2.id
        """
    )
    # ③ 唯一索引（幂等：已存在则跳过）
    if not _has_index("student_score", "uq_student_score_unique"):
        op.create_unique_constraint(
            "uq_student_score_unique",
            "student_score",
            ["student_id", "course_name", "semester"],
        )


def downgrade() -> None:
    if _has_index("student_score", "uq_student_score_unique"):
        op.drop_constraint("uq_student_score_unique", "student_score", type_="unique")
