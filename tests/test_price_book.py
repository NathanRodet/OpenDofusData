"""Tests of the price book."""

import sqlite3
from datetime import datetime, timezone

import pytest

from opendofusdata.price_book import PriceBook
from opendofusdata.records import LotPrice, MarketStats
from opendofusdata.storage import PriceStore

UTC = timezone.utc


def stats(item_id: int, server: str, median: int, mean: int, captured_at: str) -> MarketStats:
    return MarketStats(item_id, server, "24h", [], median, mean, 3, captured_at, captured_at, captured_at)


@pytest.fixture
def connection(tmp_path):
    store = PriceStore(str(tmp_path / "p.db"))
    store.save_lot_price(LotPrice(7, "Brial", 1, 100, "2026-11-12T10:00:00Z"))
    store.save_lot_price(LotPrice(7, "Brial", 1, 120, "2026-11-12T12:00:00Z"))
    store.save_lot_price(LotPrice(7, "Brial", 10, 1100, "2026-11-12T12:00:00Z"))
    store.save_lot_price(LotPrice(7, "Kourial", 1, 999, "2026-11-12T13:00:00Z"))
    store.save_market_stats(stats(7, "Brial", 110, 115, "2026-11-12T12:00:00Z"))
    yield store.connection
    store.close()


def test_the_latest_price_and_statistics_are_per_server(connection) -> None:
    book = PriceBook.load(connection, "Brial")
    assert book.unit_price(7, "last") == 120.0
    assert book.unit_price(7, "median") == 110.0
    assert book.unit_price(7, "mean") == 115.0
    assert book.prices_of(7).lots == {1: 120, 10: 1100}
    assert book.prices_of(99) is None


def test_the_other_server_is_ignored(connection) -> None:
    assert PriceBook.load(connection, "Kourial").unit_price(7, "last") == 999.0


def test_price_at_gives_the_price_known_at_that_moment(connection) -> None:
    book = PriceBook.load(connection, "Brial")
    assert book.price_at(7, datetime(2026, 11, 12, 11, 0, tzinfo=UTC)) == 100.0
    assert book.price_at(7, datetime(2026, 11, 12, 9, 0, tzinfo=UTC)) is None
    assert book.price_at(404, datetime(2026, 11, 12, 11, 0, tzinfo=UTC)) is None


def test_a_database_without_the_tables_raises(tmp_path) -> None:
    empty = sqlite3.connect(str(tmp_path / "empty.db"))
    with pytest.raises(sqlite3.OperationalError):
        PriceBook.load(empty, "Brial")
    empty.close()
