"""M5 智能报告模块 — 阶段4 下钻与脱敏验证（v6.11.0 快照口径）。"""
import pytest

from app.core.exceptions import ForbiddenError
from app.models.user import User
from app.services.report_drilldown import (
    customer_drilldown,
    filter_psych_cases,
    mask_phone,
    psych_cases_snapshot,
    special_cases_snapshot,
)
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset


def _user(user_type: str, user_id: int = 1) -> User:
    return User(id=user_id, username=f"u{user_id}", password_hash="x", real_name="t", user_type=user_type)


def test_mask_phone():
    assert mask_phone("13800000001") == "138****0001"
    assert mask_phone("123456") == "123456"  # 过短不脱敏
    assert mask_phone(None) is None


def test_customer_drilldown_masked():
    ds = build_mock_dataset()
    items = customer_drilldown(ds)
    assert len(items) == 13  # 去重后的有效客户
    phones = [i["phone"] for i in items]
    assert all("****" in p for p in phones)  # 全部脱敏
    assert "13800000001" not in phones  # 无明文手机号
    # v6.11.0：下钻补负责人与最新研判时间，不暴露画像判断依据
    assert "owner_employee_id" in items[0] and "latest_assessment_at" in items[0]


def test_psych_snapshot_has_full_detail():
    """心理个案快照含身份/联系方式/原文/历史（v6.11.0 §2.5）。"""
    ds = build_mock_dataset()
    cases = psych_cases_snapshot(ds, PERIOD_START, PERIOD_END)
    assert len(cases) == 4  # 按学生去重
    one = next(c for c in cases if c["history"])
    assert {"student_id", "student_name", "student_contact", "feedback_summary",
            "responsible_employee_id", "history"} <= set(one.keys())
    assert isinstance(one["history"], list)
    # 联系方式脱敏后入库（快照只落脱敏值）
    for c in cases:
        if c["student_contact"]:
            assert "****" in c["student_contact"]


def test_psych_cases_manager_sees_all():
    ds = build_mock_dataset()
    cases = psych_cases_snapshot(ds, PERIOD_START, PERIOD_END)
    items = filter_psych_cases(cases, _user("MANAGER"))
    assert len(items) == 4  # s2 去重


def test_psych_cases_employee_sees_own():
    ds = build_mock_dataset()
    cases = psych_cases_snapshot(ds, PERIOD_START, PERIOD_END)
    # s1(负责1) + s4(负责1)
    items = filter_psych_cases(cases, _user("EMPLOYEE", user_id=1))
    assert {i["student_id"] for i in items} == {1, 4}

    items2 = filter_psych_cases(cases, _user("EMPLOYEE", user_id=2))
    assert {i["student_id"] for i in items2} == {2}

    items3 = filter_psych_cases(cases, _user("EMPLOYEE", user_id=999))
    assert items3 == []


def test_psych_cases_other_roles_denied():
    ds = build_mock_dataset()
    cases = psych_cases_snapshot(ds, PERIOD_START, PERIOD_END)
    for ut in ("PROSPECT", "STUDENT"):
        with pytest.raises(ForbiddenError):
            filter_psych_cases(cases, _user(ut))


def test_special_cases_ai_judged_with_full_detail():
    """投诉特别案例：一期由 AI 判定（无需人工复核），快照允许完整详情（v6.11.0 §2.6）。"""
    ds = build_mock_dataset()
    items = special_cases_snapshot(ds)
    assert len(items) >= 1
    first = items[0]
    assert {"ticket_id", "student_id", "content", "detail", "ai_summary", "status"} <= set(first.keys())
    # 联系方式脱敏后才进快照
    if first["student_contact"]:
        assert "****" in first["student_contact"]
