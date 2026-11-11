"""Tests for the SQLite price store and its threaded writer."""

import logging
import sqlite3
import threading
from collections.abc import Iterator

import pytest

from opendofusdata.storage import LotPrice, MarketStats, PriceStore, StoreWriter


@pytest.fixture
def store(tmp_path) -> Iterator[PriceStore]:
    price_store = PriceStore(str(tmp_path / "prices.db"))
    yield price_store
    price_store.close()


def make_lot(price: int, captured_at: str, lot_size: int = 1, item_id: int = 100, server: str = "Ilyzaelle") -> LotPrice:
    return LotPrice(item_id, server, lot_size, price, captured_at)


def make_stats(period: str = "7d", captured_at: str = "2026-11-09T10:00:00Z") -> MarketStats:
    return MarketStats(
        item_id=100, server="Ilyzaelle", period=period, points=[(1700000000, 50, 2), (1700086400, 55, 5)],
        median=52, mean=53, sold_count=7, server_updated_at="2026-11-09T09:00:00Z",
        last_purchase_at="2026-11-08T20:00:00Z", captured_at=captured_at,
    )


def test_history_keeps_every_capture(store: PriceStore) -> None:
    store.save_lot_price(make_lot(100, "2026-11-09T10:00:00Z"))
    store.save_lot_price(make_lot(100, "2026-11-09T10:00:00Z"))
    assert len(store.price_history(100, 1)) == 2


def test_price_history_is_oldest_first(store: PriceStore) -> None:
    store.save_lot_price(make_lot(2, "2026-11-09T12:00:00Z"))
    store.save_lot_price(make_lot(1, "2026-11-09T10:00:00Z"))
    assert [lot.price for lot in store.price_history(100, 1)] == [1, 2]
    assert [lot.price for lot in store.iter_lot_prices()] == [1, 2]


def test_latest_prices_returns_most_recent_per_lot_size(store: PriceStore) -> None:
    store.save_lot_price(make_lot(10, "2026-11-09T10:00:00Z", lot_size=1))
    store.save_lot_price(make_lot(12, "2026-11-09T11:00:00Z", lot_size=1))
    store.save_lot_price(make_lot(90, "2026-11-09T10:00:00Z", lot_size=10))
    store.save_lot_price(make_lot(5, "2026-11-09T10:00:00Z", item_id=200))
    latest = store.latest_prices()
    assert [(lot.item_id, lot.lot_size, lot.price) for lot in latest] == [(100, 1, 12), (100, 10, 90), (200, 1, 5)]
    assert [lot.item_id for lot in store.latest_prices(200)] == [200]


def test_latest_prices_tie_goes_to_latest_insert(store: PriceStore) -> None:
    store.save_lot_price(make_lot(1, "2026-11-09T10:00:00Z"))
    store.save_lot_price(make_lot(2, "2026-11-09T10:00:00Z"))
    assert store.latest_prices()[0].price == 2


def test_lot_size_outside_lot_sizes_is_rejected(store: PriceStore) -> None:
    with pytest.raises(ValueError):
        store.save_lot_price(make_lot(1, "2026-11-09T10:00:00Z", lot_size=5))


def test_market_period_outside_allowed_is_rejected(store: PriceStore) -> None:
    with pytest.raises(ValueError):
        store.save_market_stats(make_stats(period="1y"))


def test_market_stats_roundtrip_keeps_points_and_dates(store: PriceStore) -> None:
    stats = make_stats()
    store.save_market_stats(stats)
    loaded = store.market_stats_history(100, "7d")
    assert loaded == [stats]
    assert all(isinstance(point, tuple) for point in loaded[0].points)
    assert loaded[0].points == [(1700000000, 50, 2), (1700086400, 55, 5)]


def test_close_twice_is_safe(tmp_path) -> None:
    price_store = PriceStore(str(tmp_path / "prices.db"))
    price_store.close()
    price_store.close()


def test_store_writer_persists_records_from_another_thread(tmp_path) -> None:
    path = str(tmp_path / "prices.db")
    writer = StoreWriter(path)
    writer.submit(make_lot(10, "2026-11-09T10:00:00Z"))
    writer.submit(make_stats())
    writer.stop()
    writer.stop()
    reader = PriceStore(path)
    try:
        assert len(reader.price_history(100, 1)) == 1
        assert len(reader.market_stats_history(100, "7d")) == 1
    finally:
        reader.close()


def test_store_writer_survives_a_bad_record(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    path = str(tmp_path / "prices.db")
    writer = StoreWriter(path)
    writer.submit(make_lot(1, "2026-11-09T10:00:00Z", lot_size=5))
    writer.submit(make_lot(2, "2026-11-09T10:00:00Z"))
    with caplog.at_level(logging.ERROR):
        writer.stop()
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    reader = PriceStore(path)
    try:
        assert [lot.price for lot in reader.price_history(100, 1)] == [2]
    finally:
        reader.close()


def test_submit_after_stop_raises(tmp_path) -> None:
    writer = StoreWriter(str(tmp_path / "prices.db"))
    writer.stop()
    with pytest.raises(RuntimeError):
        writer.submit(make_lot(1, "2026-11-09T10:00:00Z"))


def test_store_writer_fails_fast_on_invalid_path(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    threads_before = threading.active_count()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.Error):
            StoreWriter(str(tmp_path / "missing_directory" / "prices.db"))
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert threading.active_count() == threads_before


def test_store_writer_survives_an_overflowing_record(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    path = str(tmp_path / "prices.db")
    writer = StoreWriter(path)
    writer.submit(make_lot(2**63, "2026-11-09T10:00:00Z"))
    writer.submit(make_lot(2, "2026-11-09T10:00:00Z"))
    with caplog.at_level(logging.ERROR):
        writer.stop()
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    reader = PriceStore(path)
    try:
        assert [lot.price for lot in reader.price_history(100, 1)] == [2]
    finally:
        reader.close()


def test_failed_open_closes_the_connection(tmp_path) -> None:
    import gc
    import sqlite3
    import warnings

    garbage = tmp_path / "garbage.db"
    garbage.write_text("not a database " * 50, encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(sqlite3.DatabaseError):
            PriceStore(str(garbage))
        gc.collect()


def test_every_connection_uses_the_long_busy_timeout(store: PriceStore) -> None:
    from opendofusdata.storage import BUSY_TIMEOUT_SECONDS

    milliseconds = store.connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert milliseconds == int(BUSY_TIMEOUT_SECONDS * 1000) == 30_000


def test_record_submitted_during_a_short_write_lock_is_saved(tmp_path) -> None:
    import sqlite3

    path = str(tmp_path / "prices.db")
    PriceStore(path).close()
    locked, release = threading.Event(), threading.Event()

    def hold_lock() -> None:
        holder = sqlite3.connect(path)
        holder.execute("BEGIN IMMEDIATE")
        locked.set()
        release.wait()
        holder.rollback()
        holder.close()

    holder_thread = threading.Thread(target=hold_lock)
    holder_thread.start()
    locked.wait()
    writer = StoreWriter(path)
    writer.submit(make_lot(7, "2026-11-09T10:00:00Z"))
    threading.Timer(0.3, release.set).start()
    writer.stop()
    holder_thread.join()
    reader = PriceStore(path)
    try:
        assert [lot.price for lot in reader.price_history(100, 1)] == [7]
    finally:
        reader.close()
