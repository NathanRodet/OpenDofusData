import logging
from datetime import datetime, timedelta, timezone

from dofus_prices.framing import Envelope
from dofus_prices.market_stats import decode_market_stats

SERVER = "Ilyzaelle"
CAPTURED_AT = "2026-11-09T12:00:00Z"
ITEM_ID = 376
LAST_DAY = datetime(2026, 11, 9, 10, 50, 9, tzinfo=timezone.utc)


def varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def varint_field(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(value)


def bytes_field(number: int, data: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(data)) + data


def point(price: int, moment: datetime, quantity: int = 1, item_id: int = ITEM_ID) -> bytes:
    text = moment.strftime("%Y-%m-%dT%H:%M:%S.901212706Z").encode()
    return (varint_field(1, price) + varint_field(2, item_id)
            + bytes_field(3, text) + varint_field(4, quantity))


def stats_envelope(hourly: list[bytes] = (), daily: list[bytes] = ()) -> Envelope:
    payload = b"".join(bytes_field(1, item) for item in hourly)
    payload += b"".join(bytes_field(3, item) for item in daily)
    return Envelope(type_name="ire", payload=payload)


def by_period(envelope: Envelope) -> dict:
    return {stats.period: stats for stats in decode_market_stats(envelope, SERVER, CAPTURED_AT)}


def test_two_single_sale_points_give_mean_and_median_of_both() -> None:
    envelope = stats_envelope(hourly=[point(91998, LAST_DAY), point(25000, LAST_DAY)])
    stats = by_period(envelope)["24h"]
    assert (stats.median, stats.mean, stats.sold_count) == (58499, 58499, 2)
    assert (stats.item_id, stats.server, stats.server_updated_at) == (ITEM_ID, SERVER, CAPTURED_AT)
    assert stats.captured_at == CAPTURED_AT


def test_median_and_mean_are_weighted_by_quantity() -> None:
    hourly = [point(10, LAST_DAY, 1), point(20, LAST_DAY, 1), point(100, LAST_DAY, 3)]
    stats = by_period(stats_envelope(hourly=hourly))["24h"]
    assert (stats.median, stats.mean, stats.sold_count) == (100, 66, 5)


def test_even_total_median_is_integer_mean_of_middle_values() -> None:
    hourly = [point(10, LAST_DAY, 2), point(21, LAST_DAY, 2)]
    assert by_period(stats_envelope(hourly=hourly))["24h"].median == 15


def test_mean_is_truncated_not_rounded() -> None:
    hourly = [point(569, LAST_DAY, 10), point(562, LAST_DAY, 3), point(576, LAST_DAY, 4)]
    stats = by_period(stats_envelope(hourly=hourly))["24h"]
    total = 569 * 10 + 562 * 3 + 576 * 4
    assert total / 17 != total // 17
    assert stats.mean == total // 17


def test_seven_day_period_uses_points_within_seven_days_of_last_point() -> None:
    daily = [point(price, LAST_DAY - timedelta(days=days))
             for price, days in ((1, 9), (2, 7), (3, 3), (4, 0))]
    result = by_period(stats_envelope(daily=daily))
    assert result["30d"].sold_count == 4
    assert result["7d"].sold_count == 3
    assert [price for _, price, _ in result["7d"].points] == [2, 3, 4]


def test_last_purchase_is_last_hourly_point_timestamp() -> None:
    hourly = [point(5, LAST_DAY), point(6, LAST_DAY - timedelta(hours=2))]
    daily = [point(7, LAST_DAY + timedelta(days=1))]
    result = by_period(stats_envelope(hourly=hourly, daily=daily))
    assert result["24h"].last_purchase_at == "2026-11-09T10:50:09Z"
    assert result["30d"].last_purchase_at == "2026-11-09T10:50:09Z"


def test_last_purchase_falls_back_to_last_daily_point_when_no_hourly_points() -> None:
    daily = [point(7, LAST_DAY - timedelta(days=1)), point(8, LAST_DAY)]
    result = by_period(stats_envelope(daily=daily))
    assert set(result) == {"7d", "30d"}
    assert result["30d"].last_purchase_at == "2026-11-09T10:50:09Z"


def test_period_without_points_is_omitted() -> None:
    assert by_period(stats_envelope(hourly=[point(5, LAST_DAY)])).keys() == {"24h"}
    assert decode_market_stats(stats_envelope(), SERVER, CAPTURED_AT) == []


def test_period_order_is_24h_7d_30d() -> None:
    envelope = stats_envelope(hourly=[point(5, LAST_DAY)], daily=[point(6, LAST_DAY)])
    periods = [stats.period for stats in decode_market_stats(envelope, SERVER, CAPTURED_AT)]
    assert periods == ["24h", "7d", "30d"]


def test_points_are_sorted_by_timestamp() -> None:
    later, earlier = LAST_DAY, LAST_DAY - timedelta(hours=3)
    stats = by_period(stats_envelope(hourly=[point(2, later, 4), point(1, earlier, 3)]))["24h"]
    assert stats.points == [(int(earlier.timestamp()), 1, 3), (int(later.timestamp()), 2, 4)]


def test_zero_total_quantity_period_is_omitted() -> None:
    assert decode_market_stats(stats_envelope(hourly=[point(5, LAST_DAY, 0)]), SERVER, CAPTURED_AT) == []


def test_unrelated_envelope_returns_empty_list() -> None:
    envelope = Envelope(type_name="jzs", payload=b"")
    assert decode_market_stats(envelope, SERVER, CAPTURED_AT) == []


def test_missing_item_or_timestamp_is_skipped_and_logged(caplog) -> None:
    no_item = varint_field(1, 5) + bytes_field(3, b"2026-11-09T10:50:09Z") + varint_field(4, 1)
    bad_time = (varint_field(1, 5) + varint_field(2, ITEM_ID) + bytes_field(3, b"garbage")
                + varint_field(4, 1))
    envelope = stats_envelope(hourly=[no_item, bad_time, point(9, LAST_DAY)])
    with caplog.at_level(logging.WARNING):
        stats = by_period(envelope)["24h"]
    assert stats.sold_count == 1
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


def test_disagreeing_items_skip_message(caplog) -> None:
    envelope = stats_envelope(hourly=[point(5, LAST_DAY)], daily=[point(6, LAST_DAY, item_id=999)])
    with caplog.at_level(logging.WARNING):
        assert decode_market_stats(envelope, SERVER, CAPTURED_AT) == []
    assert any("ire" in record.getMessage() for record in caplog.records)


def test_truncated_payload_is_skipped_without_raising(caplog) -> None:
    payload = stats_envelope(hourly=[point(5, LAST_DAY)]).payload[:-3]
    with caplog.at_level(logging.WARNING):
        assert decode_market_stats(Envelope("ire", payload), SERVER, CAPTURED_AT) == []
    assert any(record.levelno == logging.WARNING for record in caplog.records)
