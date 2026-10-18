"""v6.11.3：M3 成绩唯一约束（student_id + course_name + semester）

Revision ID: 005_score_unique
Revises: 004_m5_drill_ticket_ai
Create Date: 2026-10-18

依据：《前端无法解决问题清单》P0#2 —— 成绩重复录入缺少服务端约束。
步骤：①存量 semester NULL 规范化为空串（MySQL 唯一索引对 NULL 不生效）
     ②清理存量重复数据（每组保留最小 id）
     ③添加唯一索引 uq_student_score_unique
"""
from alembic import op

revision = "005_score_unique"
down_revision = "004_m5_drill_ticket_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    # ③ 唯一索引
    op.create_unique_constraint(
        "uq_student_score_unique",
        "student_score",
        ["student_id", "course_name", "semester"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_student_score_unique", "student_score", type_="unique")
