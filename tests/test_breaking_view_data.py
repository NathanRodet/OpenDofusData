"""Tests of the Brisage view data (Cape Maj'Hic example)."""

import pytest

from opendofusdata.breaking_view_data import breaking_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.records import BrokenItem, LotPrice, MarketStats
from opendofusdata.storage import PriceStore

CAPE = 5000
SAC = 5001
RUNES = ((1557, 3), (1522, 12), (1519, 9))
NAMES = {CAPE: "Cape Maj'Hic", SAC: "Sac-Cawotte", 1557: "Ga Pa", 1522: "Ine", 1519: "Ba"}


def name_of(item_id: int) -> str:
    return NAMES.get(item_id, "N/A")


def lot(item_id: int, price: int) -> LotPrice:
    return LotPrice(item_id, "Brial", 1, price, "2026-11-12T09:00:00Z")


@pytest.fixture
def store(tmp_path):
    store = PriceStore(str(tmp_path / "p.db"))
    for item_id, price in ((CAPE, 20000), (1557, 11200), (1522, 100), (1519, 120)):
        store.save_lot_price(lot(item_id, price))
    store.save_market_stats(MarketStats(CAPE, "Brial", "24h", [], 19000, 19400, 5, "t", "t", "2026-11-12T09:00:00Z"))
    yield store
    store.close()


def broken(item_id: int, coefficient: float, stamp: str, server: str = "Brial") -> BrokenItem:
    return BrokenItem(server, item_id, 1, coefficient, RUNES, f"2026-11-12T{stamp}:00Z")


def rows_of(store: PriceStore, window=(None, None)):
    book = PriceBook.load(store.connection, "Brial")
    return breaking_rows(store.connection, "Brial", window, name_of, book, "last"), book


def test_a_cape_row_has_its_values_and_plus_value(store) -> None:
    store.save_record(broken(CAPE, 0.44, "10:00"))
    (row,), _ = rows_of(store)
    assert row.name == "Cape Maj'Hic"
    assert row.runes_value.total == 35880.0 and not row.runes_value.partial
    assert (row.estimated_value, row.hdv_value, row.plus_value) == (19400.0, 20000.0, 15880.0)


def test_an_unpriced_object_has_no_plus_value_and_comes_last(store) -> None:
    store.save_record(broken(SAC, 0.26, "11:00"))
    store.save_record(broken(CAPE, 0.44, "10:00"))
    rows, _ = rows_of(store)
    assert [row.item_id for row in rows] == [CAPE, SAC]
    assert rows[1].plus_value is None and rows[1].runes_value.total == 35880.0


def test_the_server_and_the_window_filter_rows(store) -> None:
    from datetime import datetime, timezone

    store.save_record(broken(CAPE, 0.44, "10:00"))
    store.save_record(broken(CAPE, 0.31, "10:00", server="Kourial"))
    rows, _ = rows_of(store, (datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc), None))
    assert rows == []
    assert len(rows_of(store)[0]) == 1


def test_the_object_hdv_value_is_the_cheapest_listing_else_the_last_sale(store) -> None:
    points = [[1_794_470_400, 195, 2], [1_794_477_600, 96, 6]]
    store.save_market_stats(MarketStats(SAC, "Brial", "24h", points, 97, 117, 16, "t", "t", "2026-11-12T09:00:00Z"))
    store.save_record(broken(SAC, 0.73, "10:00"))
    assert rows_of(store)[0][0].hdv_value == 96.0
    store.save_lot_price(lot(SAC, 100))
    assert rows_of(store)[0][0].hdv_value == 100.0
