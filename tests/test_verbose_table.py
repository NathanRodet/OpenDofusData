"""Tests for the pure text tables shown by run --verbose."""

from opendofusdata.records import LotPrice, MarketStats
from opendofusdata.verbose_table import format_lot_prices, format_market_stats, group_thousands

CAPTURED_AT = "2026-11-10T10:29:17Z"
LAST_PURCHASE = "2026-11-10T09:43:01Z"


def lots(item: int, prices: dict[int, int]) -> list[LotPrice]:
    return [LotPrice(item, "Ilyzaelle", size, price, CAPTURED_AT) for size, price in prices.items()]


def stats_row(period: str, median: int, mean: int, sold: int) -> MarketStats:
    return MarketStats(307, "Ilyzaelle", period, [], median, mean, sold, CAPTURED_AT, LAST_PURCHASE, CAPTURED_AT)


def test_group_thousands_uses_plain_spaces() -> None:
    assert [group_thousands(value) for value in (0, 750, 5868, 1234567)] == ["0", "750", "5 868", "1 234 567"]


def test_lot_block_of_item_307() -> None:
    text = format_lot_prices(lots(307, {1: 750, 10: 5868, 100: 49993, 1000: 499999}))
    assert text == (
        "Lots - objet 307 (10:29:17 UTC)\n"
        "  lot      prix\n"
        "    1       750\n"
        "   10     5 868\n"
        "  100    49 993\n"
        " 1000   499 999"
    )


def test_lot_block_with_a_subset_of_lots() -> None:
    text = format_lot_prices(lots(376, {1: 145, 10: 1872, 100: 12989}))
    assert text == (
        "Lots - objet 376 (10:29:17 UTC)\n"
        "  lot      prix\n"
        "    1       145\n"
        "   10     1 872\n"
        "  100    12 989"
    )


def test_very_large_price_keeps_columns_aligned() -> None:
    text = format_lot_prices(lots(1, {1: 9999999999, 10: 5}))
    rows = text.splitlines()[1:]
    assert {len(row) for row in rows} == {len(rows[0])}
    assert rows[1].endswith("9 999 999 999") and rows[2].endswith("5")


def test_stats_block_of_item_307() -> None:
    text = format_market_stats([
        stats_row("24h", 584, 568, 1177), stats_row("7d", 521, 486, 15998), stats_row("30d", 324, 358, 79129),
    ])
    assert text == (
        "Cours du marché - objet 307 (10:29:17 UTC)\n"
        "  période   médiane   moyenne    vendus   dernier achat (UTC)\n"
        "  24h           584       568     1 177   2026-11-10 09:43\n"
        "  7j            521       486    15 998   2026-11-10 09:43\n"
        "  30j           324       358    79 129   2026-11-10 09:43"
    )


def test_stats_block_keeps_alignment_with_huge_values() -> None:
    rows = format_market_stats([stats_row("24h", 10**10, 5, 10**9)]).splitlines()[1:]
    assert rows[0].index("dernier") == rows[1].index("2026")


def test_empty_lists_give_empty_text() -> None:
    assert format_lot_prices([]) == ""
    assert format_market_stats([]) == ""


def test_non_standard_last_purchase_is_shown_as_is() -> None:
    row = stats_row("24h", 1, 2, 3)
    row.last_purchase_at = "yesterday"
    assert format_market_stats([row]).endswith("3   yesterday")
