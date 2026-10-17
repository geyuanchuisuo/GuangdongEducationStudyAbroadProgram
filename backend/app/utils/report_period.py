"""M5 智能报告模块 — 周期计算与合法性校验（统一北京时间）。

项目统一使用 naive datetime 表示北京时间（Asia/Shanghai）。
周期边界：自然周为周一至周日，自然月为每月 1 日至月末；
起点包含、终点开区间（下一个周期起点不包含）。
"""
from datetime import datetime, timedelta


class PeriodValidationError(ValueError):
    """周期不合法（对齐/未来/跨度错误）——服务层转 40002。"""


def week_range(anchor: datetime) -> tuple[datetime, datetime]:
    """anchor 所在自然周：[周一 00:00, 下周一 00:00)。"""
    monday = (anchor - timedelta(days=anchor.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday, monday + timedelta(days=7)


def month_range(anchor: datetime) -> tuple[datetime, datetime]:
    """anchor 所在自然月：[1 日 00:00, 下月 1 日 00:00)。"""
    start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1)
    else:
        end = datetime(start.year, start.month + 1, 1)
    return start, end


def _is_week(start: datetime, end: datetime) -> bool:
    return (
        start.weekday() == 0
        and (end - start) == timedelta(days=7)
        and start == start.replace(hour=0, minute=0, second=0, microsecond=0)
    )


def _is_month(start: datetime, end: datetime) -> bool:
    return (
        start.day == 1
        and start == start.replace(hour=0, minute=0, second=0, microsecond=0)
        and month_range(start)[1] == end
    )


def validate_period(
    start: datetime,
    end: datetime,
    now: datetime | None = None,
    check_future: bool = True,
) -> None:
    """周期合法性校验（M5-04.2）。

    规则：
    - start < end 且跨度 ≤ 31 天（自然月上限）
    - 必须对齐自然周（周一 00:00 起 7 天）或自然月（1 日 00:00 起整月）边界；
      对齐自然周/月即允许合理跨年（如 12 月末周、12 月自然月）
    - 不允许未来周期（end 不得超过当前时刻）；mock 演示数据可豁免
      （check_future=False，其参考周期是固定演示周期，不受真实时钟约束）
    """
    now = now or datetime.now()
    if start >= end:
        raise PeriodValidationError("周期起点必须早于终点")
    if (end - start) > timedelta(days=31):
        raise PeriodValidationError("周期跨度超过 31 天，仅支持自然周或自然月")
    if not (_is_week(start, end) or _is_month(start, end)):
        raise PeriodValidationError(
            "周期未对齐边界：仅支持自然周（周一 00:00 起 7 天）或自然月（1 日 00:00 起整月）"
        )
    if check_future and end > now:
        raise PeriodValidationError("不允许生成未来周期的报告")


def default_completed_week(now: datetime | None = None) -> tuple[datetime, datetime]:
    """上一完整自然周：[上周一 00:00, 本周一 00:00)。

    生产报告的手动生成缺省周期必须用它（M5-10.8）：`week_range(now)` 的终点是
    下周一 00:00（恒晚于当前时刻），直接送校验会被 `check_future` 拒成 40002。
    """
    now = now or datetime.now()
    this_monday = week_range(now)[0]
    return this_monday - timedelta(days=7), this_monday