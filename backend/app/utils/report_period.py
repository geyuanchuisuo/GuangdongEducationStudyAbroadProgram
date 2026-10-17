"""M5 智能报告模块 — 周期计算工具（统一北京时间）。

项目统一使用 naive datetime 表示北京时间（Asia/Shanghai）。
周期边界：自然周为周一至周日，自然月为每月 1 日至月末；
起点包含、终点开区间（下一个周期起点不包含）。
"""
from datetime import datetime, timedelta


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
