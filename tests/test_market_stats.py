import logging
from datetime import datetime, timedelta, timezone

from dofus_prices.framing import Envelope
from dofus_prices.market_stats import decode_market_stats
from dofus_prices.records import MarketStats
from dofus_prices.timeutil import format_utc

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


def stats_at(envelope: Envelope, captured_at: str) -> dict:
    return {stats.period: stats for stats in decode_market_stats(envelope, SERVER, captured_at)}


def utc(day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, second, tzinfo=timezone.utc)


def seven_day_prices(moments: list[datetime], captured_at: str) -> list[int]:
    """Prices (1, 2, 3...) of the daily points kept in the 7d period."""
    daily = [point(price, moment) for price, moment in enumerate(moments, start=1)]
    result = stats_at(stats_envelope(daily=daily), captured_at)
    return [price for _, price, _ in result["7d"].points] if "7d" in result else []


def test_seven_day_window_starts_at_midnight_utc_seven_days_before_capture() -> None:
    moments = [utc(2, 23, 59, 59), utc(3, 0, 0, 0), utc(3, 0, 0, 1), utc(10, 9)]
    assert seven_day_prices(moments, "2026-11-10T20:16:17Z") == [2, 3, 4]


def test_capture_shortly_after_midnight_uses_the_new_date() -> None:
    moments = [utc(3, 23, 59, 59), utc(4, 0, 0, 0), utc(10, 0, 0, 5)]
    assert seven_day_prices(moments, "2026-11-11T00:00:07Z") == [2, 3]


def test_window_is_anchored_on_capture_not_on_last_daily_point() -> None:
    assert seven_day_prices([utc(1, 12), utc(2, 12)], "2026-11-10T12:00:00Z") == []


def test_fewer_than_seven_days_of_data_keeps_every_point() -> None:
    moments = [utc(8, 10), utc(9, 10), utc(10, 10)]
    assert seven_day_prices(moments, "2026-11-10T12:00:00Z") == [1, 2, 3]


def test_single_point_gives_a_seven_day_period() -> None:
    assert seven_day_prices([utc(10, 9)], "2026-11-10T12:00:00Z") == [1]


def test_unparsable_captured_at_anchors_on_last_daily_point_and_warns(caplog) -> None:
    moments = [utc(2, 23, 59, 59), utc(3, 0, 0, 0), utc(10, 9)]
    with caplog.at_level(logging.WARNING):
        prices = seven_day_prices(moments, "not a date")
    assert prices == [2, 3]
    assert "captured_at" in caplog.text


# Real daily points [unix seconds, price, quantity] copied from the owner's database.
VOLKORNE_POINTS = [[1791828547,4981,400],[1791931304,5370,100],[1792001143,5379,60],[1792105633,5261,32],[1792192046,5788,578],[1792266741,6308,16],[1792312697,5990,10],[1792450137,6399,20],[1792505149,6416,120],[1792621834,6399,110],[1792704127,5780,10],[1792773909,6344,220],[1792874893,5685,392],[1792958088,6353,161],[1793036385,6395,125],[1793088040,6399,20],[1793309223,6399,302],[1793403252,6384,127],[1793529659,6392,13],[1793636924,5999,2],[1793723016,6047,21],[1793815707,6555,1],[1793916428,4413,80],[1793996284,5989,40],[1794091398,5997,251],[1794173026,5989,201],[1794253013,5849,100],[1794331355,5700,30]]
DRAGODINDE_POINTS = [[1791812441,6000,11],[1791904634,9899,22],[1791984436,19633,15],[1792336971,18713,70],[1792402925,17988,1],[1792540067,14353,45],[1792565897,13899,30],[1792710199,19670,131],[1792752949,12965,13],[1792863559,12958,11],[1792940959,13420,81],[1793045323,12768,13],[1793192497,11999,3],[1793306016,10999,1],[1793391478,13271,11],[1793566318,11216,23],[1793661444,11165,54],[1793670657,11099,10],[1793828661,11630,57],[1793916422,12698,20],[1793984310,13499,10],[1794087781,13899,14],[1794135301,14997,1]]
MIDNIGHT_2026_11_03 = 1793664000


def real_seven_day_stats(points: list[list[int]], item_id: int, captured_at: str,
                         expected: tuple[int, int, int]) -> None:
    """Assert the whole 7d MarketStats built from real points."""
    daily = [point(price, datetime.fromtimestamp(stamp, timezone.utc), quantity, item_id)
             for stamp, price, quantity in points]
    kept = [tuple(row) for row in points if row[0] >= MIDNIGHT_2026_11_03]
    last_day = format_utc(datetime.fromtimestamp(points[-1][0], timezone.utc))
    median, mean, sold = expected
    result = stats_at(stats_envelope(daily=daily), captured_at)["7d"]
    assert result == MarketStats(item_id, SERVER, "7d", kept, median, mean, sold,
                                 captured_at, last_day, captured_at)


def test_real_item_32526_matches_the_game_screen() -> None:
    real_seven_day_stats(VOLKORNE_POINTS, 32526, "2026-11-10T20:16:17Z", (5989, 5788, 724))


def test_real_item_32525_prediction() -> None:
    # Predicted by the same rule, NOT yet confirmed on the game screen.
    real_seven_day_stats(DRAGODINDE_POINTS, 32525, "2026-11-10T20:14:59Z", (11630, 12253, 112))


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
