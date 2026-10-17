"""M5 智能报告模块 — 阶段4 下钻与脱敏验证。"""
import pytest

from app.core.exceptions import ForbiddenError
from app.models.user import User
from app.services.report_drilldown import (
    customer_drilldown,
    mask_phone,
    psych_cases_for_user,
    special_cases_drilldown,
)
from app.services.report_mock_data import PERIOD_END, PERIOD_START, build_mock_dataset


def _user(user_type: str, user_id: int = 1) -> User:
    return User(id=user_id, username=f"u{user_id}", password_hash="x", real_name="t", user_type=user_type)


def test_mask_phone():
    assert mask_phone("13800000001") == "138****0001"
    assert mask_phone("123456") == "123456"  # 过短不脱敏


def test_customer_drilldown_masked():
    ds = build_mock_dataset()
    items = customer_drilldown(ds)
    assert len(items) == 13  # 去重后的有效客户
    phones = [i["phone"] for i in items]
    assert all("****" in p for p in phones)  # 全部脱敏
    assert "13800000001" not in phones  # 无明文手机号


def test_psych_cases_manager_sees_all():
    ds = build_mock_dataset()
    items = psych_cases_for_user(ds, PERIOD_START, PERIOD_END, _user("MANAGER"))
    assert len(items) == 4  # s2 去重


def test_psych_cases_employee_sees_own():
    ds = build_mock_dataset()
    # s1(负责1) + s4(负责1)
    items = psych_cases_for_user(ds, PERIOD_START, PERIOD_END, _user("EMPLOYEE", user_id=1))
    assert {i["student_id"] for i in items} == {1, 4}

    # 负责 id=2 只有 s2
    items2 = psych_cases_for_user(ds, PERIOD_START, PERIOD_END, _user("EMPLOYEE", user_id=2))
    assert {i["student_id"] for i in items2} == {2}

    # 无负责关系 -> 空
    items3 = psych_cases_for_user(ds, PERIOD_START, PERIOD_END, _user("EMPLOYEE", user_id=999))
    assert items3 == []


def test_psych_cases_other_roles_denied():
    ds = build_mock_dataset()
    for ut in ("PROSPECT", "STUDENT"):
        with pytest.raises(ForbiddenError):
            psych_cases_for_user(ds, PERIOD_START, PERIOD_END, _user(ut))


def test_special_cases_only_approved():
    ds = build_mock_dataset()
    items = special_cases_drilldown(ds)
    assert len(items) == 1  # 仅 t10 复核通过
    assert set(items[0].keys()) == {"ticket_id", "owner_id", "progress"}  # 不含个人/原文
    assert items[0]["ticket_id"] == 10
