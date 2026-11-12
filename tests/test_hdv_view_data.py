"""Tests of the HDV view data read through a real database."""

from datetime import datetime, timezone

import pytest

from opendofusdata.hdv_view_data import hdv_detail, hdv_rows
from opendofusdata.records import LotPrice, MarketStats
from opendofusdata.storage import PriceStore

UTC = timezone.utc
FLECHE = 3000
SALIKRONE = 3001
POINT_TIMES = (1_794_470_400, 1_794_474_000, 1_794_477_600)


def name_of(item_id: int) -> str:
    return {FLECHE: "Flèche du Chafer Archer", SALIKRONE: "Salikrone"}.get(item_id, "N/A")


def type_of(item_id: int) -> str:
    return "Ressource"


@pytest.fixture
def store(tmp_path):
    store = PriceStore(str(tmp_path / "p.db"))
    yield store
    store.close()


def save_stats(store: PriceStore, item_id: int, server: str, captured_at: str, median=0, mean=0, sold=108) -> None:
    points = [[seconds, 100 + index, index + 1] for index, seconds in enumerate(POINT_TIMES)]
    store.save_market_stats(MarketStats(item_id, server, "24h", points, median, mean, sold,
                                        captured_at, captured_at, captured_at))


def test_a_window_excludes_items_captured_before_it(store) -> None:
    store.save_lot_price(LotPrice(SALIKRONE, "Brial", 1, 500, "2026-11-10T10:00:00Z"))
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 80, "2026-11-12T10:00:00Z"))
    window = (datetime(2026, 11, 12, 0, 0, tzinfo=UTC), None)
    rows = hdv_rows(store.connection, "Brial", window, name_of, type_of)
    assert [row.item_id for row in rows] == [FLECHE]


def test_two_servers_are_separated(store) -> None:
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 80, "2026-11-12T10:00:00Z"))
    store.save_lot_price(LotPrice(SALIKRONE, "Kourial", 1, 90, "2026-11-12T10:00:00Z"))
    rows = hdv_rows(store.connection, "Kourial", (None, None), name_of, type_of)
    assert [row.item_id for row in rows] == [SALIKRONE]


def test_the_fleche_statistics_are_returned_unchanged(store) -> None:
    save_stats(store, FLECHE, "Brial", "2026-11-12T10:00:00Z")
    (row,) = hdv_rows(store.connection, "Brial", (None, None), name_of, type_of)
    assert (row.median_24h, row.sold_24h, row.last_price) == (0, 108, None)
    assert row.last_seen == datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


def test_rows_show_the_latest_lot_one_price_and_come_newest_first(store) -> None:
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 80, "2026-11-12T09:00:00Z"))
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 95, "2026-11-12T10:00:00Z"))
    store.save_lot_price(LotPrice(SALIKRONE, "Brial", 1, 500, "2026-11-12T11:00:00Z"))
    rows = hdv_rows(store.connection, "Brial", (None, None), name_of, type_of)
    assert [(row.item_id, row.last_price) for row in rows] == [(SALIKRONE, 500), (FLECHE, 95)]


def test_the_curve_comes_back_in_time_order(store) -> None:
    save_stats(store, FLECHE, "Brial", "2026-11-12T10:00:00Z")
    curve = hdv_detail(store.connection, "Brial", FLECHE, name_of, type_of).curves["24h"]
    assert [point.price for point in curve] == [100, 101, 102]
    assert curve[0].moment == datetime.fromtimestamp(POINT_TIMES[0], UTC)


def test_detail_lots_and_history(store) -> None:
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 80, "2026-11-12T09:00:00Z"))
    store.save_lot_price(LotPrice(FLECHE, "Brial", 10, 700, "2026-11-12T09:00:00Z"))
    store.save_lot_price(LotPrice(FLECHE, "Brial", 1, 95, "2026-11-12T10:00:00Z"))
    detail = hdv_detail(store.connection, "Brial", FLECHE, name_of, type_of)
    assert detail.lots == {1: 95, 10: 700}
    assert detail.history[0].price == 95 and len(detail.history) == 3


def test_empty_database_and_unknown_item(store) -> None:
    assert hdv_rows(store.connection, "Brial", (None, None), name_of, type_of) == []
    detail = hdv_detail(store.connection, "Brial", 12345, name_of, type_of)
    assert (detail.stats, detail.curves, detail.lots, detail.history) == ({}, {}, {}, [])
