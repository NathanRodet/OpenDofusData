"""Tests of the period windows and the elapsed time text."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from opendofusdata.time_filters import (
    PERIOD_ALL, PERIOD_CUSTOM, PERIOD_LAST_HOUR, PERIOD_MONTH, PERIOD_SIX_HOURS, PERIOD_TODAY, PERIOD_WEEK,
    PERIODS, PeriodSelection, elapsed_text, local_text, parse_stored, period_window,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 12, 18, 42, tzinfo=UTC)


def test_periods_are_listed_in_display_order() -> None:
    assert PERIODS == (PERIOD_LAST_HOUR, PERIOD_SIX_HOURS, PERIOD_TODAY, PERIOD_WEEK, PERIOD_MONTH,
                       PERIOD_ALL, PERIOD_CUSTOM)


def test_last_hour_starts_sixty_minutes_ago() -> None:
    start, end = period_window(PeriodSelection(PERIOD_LAST_HOUR), NOW)
    assert (start, end) == (NOW - timedelta(minutes=60), None)


def test_relative_periods() -> None:
    assert period_window(PeriodSelection(PERIOD_SIX_HOURS), NOW)[0] == NOW - timedelta(hours=6)
    assert period_window(PeriodSelection(PERIOD_WEEK), NOW)[0] == NOW - timedelta(days=7)
    assert period_window(PeriodSelection(PERIOD_MONTH), NOW)[0] == NOW - timedelta(days=30)


def test_today_starts_at_local_midnight_converted_to_utc() -> None:
    zone = timezone(timedelta(hours=1))
    now = datetime(2026, 11, 12, 23, 30, tzinfo=UTC)
    assert period_window(PeriodSelection(PERIOD_TODAY), now, zone)[0] == datetime(2026, 11, 12, 23, 0, tzinfo=UTC)


def test_today_on_a_dst_change_day() -> None:
    zone = ZoneInfo("Europe/Paris")
    now = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    assert period_window(PeriodSelection(PERIOD_TODAY), now, zone)[0] == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)


def test_all_has_no_bounds() -> None:
    assert period_window(PeriodSelection(PERIOD_ALL), NOW) == (None, None)


def test_custom_uses_its_bounds() -> None:
    start, end = NOW - timedelta(days=3), NOW - timedelta(days=1)
    assert period_window(PeriodSelection(PERIOD_CUSTOM, start, end), NOW) == (start, end)


def test_elapsed_text() -> None:
    cases = [(timedelta(seconds=30), "il y a 1 min"), (timedelta(minutes=12), "il y a 12 min"),
             (timedelta(minutes=59), "il y a 59 min"), (timedelta(minutes=60), "il y a 1 h"),
             (timedelta(hours=5, minutes=59), "il y a 5 h"), (timedelta(hours=24), "il y a 1 j"),
             (timedelta(hours=49), "il y a 2 j"), (timedelta(minutes=-5), "il y a 1 min")]
    for elapsed, expected in cases:
        assert elapsed_text(NOW - elapsed, NOW) == expected


def test_local_text_and_parse_stored() -> None:
    moment = parse_stored("2026-11-12T17:42:09Z")
    assert moment == datetime(2026, 11, 12, 17, 42, 9, tzinfo=UTC)
    assert local_text(moment, timezone(timedelta(hours=1))) == "12/11 18:42"


def test_stored_bounds_are_sortable_text() -> None:
    from opendofusdata.time_filters import stored_bounds

    start = datetime(2026, 11, 12, 9, 5, tzinfo=UTC)
    assert stored_bounds((start, None))[0] == "2026-11-12T09:05:00Z"
    low, high = stored_bounds((None, None))
    assert low < "2026-11-12T09:05:00Z" < high
