"""Tests of the bounded log feed and its row formatting."""

from datetime import datetime, timezone

from opendofusdata.log_feed import (
    LOG_COLUMN_WIDTHS, LOG_COLUMNS, FeedWriter, LogFeed, entry_from_record, format_log_line,
    format_log_row, format_number, shorten,
)
from opendofusdata.records import LotPrice, MarketStats

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)


def lot(item_id: int = 307, size: int = 10, price: int = 5868) -> LotPrice:
    return LotPrice(item_id, "Brial", size, price, "2026-11-11T13:32:05Z")


def stats(period: str = "7d", median: int = 46) -> MarketStats:
    return MarketStats(307, "Brial", period, [], median, 40, 12, "", "", "2026-11-11T13:32:05Z")


def shown_feed(capacity: int = 200) -> LogFeed:
    feed = LogFeed(capacity)
    feed.set_visible(True)
    return feed


def test_hidden_feed_accumulates_nothing() -> None:
    feed = LogFeed()
    feed.add(lot(), MOMENT)
    assert feed.entries() == []


def test_shown_feed_keeps_newest_first() -> None:
    feed = shown_feed()
    feed.add(lot(1), MOMENT)
    feed.add(lot(2), MOMENT)
    assert [entry.item_id for entry in feed.entries()] == [2, 1]


def test_capacity_is_bounded() -> None:
    feed = shown_feed(3)
    for item_id in range(5):
        feed.add(lot(item_id), MOMENT)
    assert [entry.item_id for entry in feed.entries()] == [4, 3, 2]


def test_showing_again_starts_empty() -> None:
    feed = shown_feed()
    feed.add(lot(), MOMENT)
    feed.set_visible(False)
    feed.set_visible(True)
    assert feed.entries() == []


def test_lot_row_format() -> None:
    entry = entry_from_record(lot(size=10, price=5868), MOMENT)
    row = format_log_row(entry, lambda item_id: "Ailes de Moskito")
    assert row[1:] == ("HDV", "Ailes de Moskito", "lot ×10", "5 868")
    assert row[0] == MOMENT.astimezone().strftime("%H:%M:%S")


def test_stats_row_labels() -> None:
    details = {period: entry_from_record(stats(period), MOMENT).detail for period in ("24h", "7d", "30d")}
    assert details == {"24h": "stats 24 h", "7d": "stats 7 j", "30d": "stats 30 j"}


def test_stats_value_is_the_median() -> None:
    assert entry_from_record(stats(median=12989), MOMENT).value == "12 989"


def test_unknown_item_is_na() -> None:
    entry = entry_from_record(lot(), MOMENT)
    assert format_log_row(entry, lambda item_id: "N/A")[2] == "N/A"


def test_format_number_groups_thousands_with_spaces() -> None:
    assert format_number(82985) == "82 985" and format_number(750) == "750"


def test_feed_writer_forwards_then_feeds() -> None:
    forwarded: list[object] = []

    class Sink:
        def submit(self, record: object) -> None:
            forwarded.append(record)

    feed = shown_feed()
    record = lot()
    FeedWriter(Sink(), feed, lambda: MOMENT).submit(record)
    assert forwarded == [record] and len(feed.entries()) == 1


def test_shorten_adds_an_ellipsis_and_never_exceeds_the_width() -> None:
    assert shorten("Âme capturée : Fourapin le Chaud", 12) == "Âme capturé…"
    assert len(shorten("x" * 100, 26)) == 26


def test_shorten_keeps_short_text_unchanged() -> None:
    assert shorten("Rune Ra Vi", 26) == "Rune Ra Vi"
    assert shorten("abc", 3) == "abc"


def test_log_line_has_fixed_width_columns_and_right_aligned_value() -> None:
    short = format_log_line(("14:32:05", "HDV", "Rune Ra Vi", "lot ×1", "1 240"))
    long = format_log_line(("14:31:40", "HDV", "Âme capturée : Fourapin le Chaud", "lot ×1", "82 985"))
    assert len(short) == len(long) == sum(LOG_COLUMN_WIDTHS) + 2 * (len(LOG_COLUMN_WIDTHS) - 1)
    assert short.endswith("   1 240") and long.endswith("  82 985")


def test_header_line_uses_the_same_widths() -> None:
    assert len(format_log_line(LOG_COLUMNS)) == len(format_log_line(("a", "b", "c", "d", "e")))


def test_every_log_column_has_a_width() -> None:
    assert len(LOG_COLUMNS) == len(LOG_COLUMN_WIDTHS)
