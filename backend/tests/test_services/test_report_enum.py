"""M5 报告类型枚举校验测试（M5-13.1 / M5-12.3）。

验证点：
1. schema 层 ReportType 为 Literal，非法值（含契约旧笔误值）在请求体校验即被拒绝
   ——经 FastAPI 映射为 HTTP 422，不会落到服务层 40002；
2. 5 个合法枚举成员与 REPORT_TYPE_NAMES（服务层分发键）完全一致，两处不会漂移。
"""
import pytest
from pydantic import ValidationError
from typing import get_args

from app.schemas.report import ReportGenerateRequest, ReportType
from app.services.report_content import REPORT_TYPE_NAMES

VALID_TYPES = [
    "customer_analysis",
    "daily_report_summary",
    "weekly_report_summary",
    "psych_weekly",
    "complaint_weekly",
]

# 契约 v2.8.7 修正前的旧笔误值（接口契约v1.md §7），以及其它非法样例
INVALID_TYPES = [
    "customer_business",   # 旧契约值
    "daily_summary",       # 旧契约值
    "daily_weekly",        # 旧契约值
    "CA",                  # 前端 tab code，不是后端枚举
    "",
    "CUSTOMER_ANALYSIS",   # 大小写敏感
]


def test_literal_members_match_service_dispatch():
    """schema Literal 成员集合 == 服务层 REPORT_TYPE_NAMES 键集合。"""
    assert set(get_args(ReportType)) == set(VALID_TYPES)
    assert set(get_args(ReportType)) == set(REPORT_TYPE_NAMES.keys())


@pytest.mark.parametrize("rt", VALID_TYPES)
def test_valid_report_type_accepted(rt):
    req = ReportGenerateRequest(report_type=rt)
    assert req.report_type == rt


@pytest.mark.parametrize("rt", INVALID_TYPES)
def test_invalid_report_type_rejected_at_schema(rt):
    """非法枚举在 pydantic 层即拒绝（FastAPI 下对应 422），不到服务层。"""
    with pytest.raises(ValidationError):
        ReportGenerateRequest(report_type=rt)
