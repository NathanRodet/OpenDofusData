from datetime import datetime, timedelta, timezone

import pytest

from dofus_prices.timeutil import format_utc, parse_server_timestamp


def test_nine_digit_fraction_is_truncated_to_microseconds() -> None:
    moment = parse_server_timestamp("2026-11-09T10:50:09.901212706Z")
    assert moment == datetime(2026, 11, 9, 10, 50, 9, 901212, tzinfo=timezone.utc)


def test_timestamp_without_fraction_is_accepted() -> None:
    assert parse_server_timestamp("2026-11-09T10:50:09Z").second == 9


@pytest.mark.parametrize("text", ["", "not a date", "2026-11-09 10:50:09Z", "2026-11-09T10:50:09"])
def test_invalid_timestamp_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        parse_server_timestamp(text)


def test_format_utc_uses_single_format() -> None:
    assert format_utc(datetime(2026, 11, 9, 10, 50, 9, 5, tzinfo=timezone.utc)) == "2026-11-09T10:50:09Z"


def test_format_utc_converts_other_offsets_to_utc() -> None:
    moment = datetime(2026, 11, 9, 11, 50, 9, tzinfo=timezone(timedelta(hours=1)))
    assert format_utc(moment) == "2026-11-09T10:50:09Z"


def test_format_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        format_utc(datetime(2026, 11, 9, 10, 50, 9))
