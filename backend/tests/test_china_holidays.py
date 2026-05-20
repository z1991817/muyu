from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.lib.china_holidays import get_china_rest_day_info

TZ = ZoneInfo("Asia/Shanghai")


def test_holiday_is_rest_day() -> None:
    info = get_china_rest_day_info(datetime(2026, 5, 1, 12, tzinfo=TZ))

    assert info.date == "2026-05-01"
    assert info.is_rest_day is True
    assert info.kind == "holiday"
    assert info.name == "劳动节"


def test_adjusted_weekend_is_workday() -> None:
    info = get_china_rest_day_info(datetime(2026, 5, 9, 12, tzinfo=TZ))

    assert info.date == "2026-05-09"
    assert info.is_rest_day is False
    assert info.kind == "workday"
    assert info.name is None


def test_regular_weekend_is_rest_day() -> None:
    info = get_china_rest_day_info(datetime(2026, 5, 10, 12, tzinfo=TZ))

    assert info.date == "2026-05-10"
    assert info.is_rest_day is True
    assert info.kind == "weekend"
    assert info.name == "周末"
