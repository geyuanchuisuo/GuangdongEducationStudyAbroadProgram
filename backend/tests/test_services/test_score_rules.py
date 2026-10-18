"""M3 成绩三件套规则（v6.11.3）——schema 边界与规范化纯逻辑验证。

HTTP 层行为（重复 40901 / PUT 200/404/422/40301）由容器内冒烟脚本覆盖，
此处锁定 Pydantic 口径：成绩范围 0-100（与前端口径统一）。
"""
import pytest
from pydantic import ValidationError

from app.schemas.employee import ScoreCreate, ScoreUpdate
from app.services.employee_service import EmployeeService


class TestScoreRange:
    def test_create_score_zero_ok(self):
        assert ScoreCreate(student_id=1, course_name="数学", score=0).score == 0

    def test_create_score_hundred_ok(self):
        assert ScoreCreate(student_id=1, course_name="数学", score=100).score == 100

    def test_create_score_over_100_rejected(self):
        with pytest.raises(ValidationError):
            ScoreCreate(student_id=1, course_name="数学", score=100.1)

    def test_create_score_negative_rejected(self):
        with pytest.raises(ValidationError):
            ScoreCreate(student_id=1, course_name="数学", score=-0.1)

    def test_update_score_range(self):
        assert ScoreUpdate(score=59.5).score == 59.5
        with pytest.raises(ValidationError):
            ScoreUpdate(score=100.01)
        with pytest.raises(ValidationError):
            ScoreUpdate(score=-1)


class TestSemesterNormalize:
    def test_none_becomes_empty(self):
        assert EmployeeService._norm_semester(None) == ""

    def test_blank_becomes_empty(self):
        assert EmployeeService._norm_semester("  ") == ""

    def test_value_trimmed(self):
        assert EmployeeService._norm_semester(" 2026春 ") == "2026春"
