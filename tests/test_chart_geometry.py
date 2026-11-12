"""Tests of the chart ticks and scaling."""

from datetime import datetime, timedelta, timezone

from opendofusdata.chart_geometry import scale, time_ticks, value_ticks

UTC = timezone.utc


def test_value_ticks_are_equally_spaced() -> None:
    ticks = value_ticks(500, 812)
    assert len(ticks) == 5
    assert (ticks[0], ticks[-1]) == (500.0, 812.0)
    assert ticks[1] - ticks[0] == ticks[2] - ticks[1]


def test_a_flat_range_is_widened() -> None:
    ticks = value_ticks(8.0, 8.0)
    assert (ticks[0], ticks[-1]) == (8.0, 9.0)


def test_scale_is_linear_and_safe_on_a_flat_range() -> None:
    assert scale(150, 100, 200, 400) == 200.0
    assert scale(5, 5, 5, 400) == 0.0


def test_ticks_over_one_day_are_four_hours_apart_with_the_date_at_midnight() -> None:
    start = datetime(2026, 11, 12, 1, 30, tzinfo=UTC)
    ticks = time_ticks(start, start + timedelta(hours=24), UTC)
    assert [label for _, label in ticks] == ["04:00", "08:00", "12:00", "16:00", "20:00", "13/11"]


def test_ticks_over_five_days_are_one_per_day() -> None:
    start = datetime(2026, 11, 8, 6, 0, tzinfo=UTC)
    ticks = time_ticks(start, start + timedelta(days=5), UTC)
    assert [label for _, label in ticks] == ["09/11", "10/11", "11/11", "12/11", "13/11"]


def test_ticks_use_the_local_zone() -> None:
    zone = timezone(timedelta(hours=1))
    start = datetime(2026, 11, 12, 22, 30, tzinfo=UTC)
    ticks = time_ticks(start, start + timedelta(hours=6), zone)
    assert [label for _, label in ticks] == ["13/11", "04:00"]
