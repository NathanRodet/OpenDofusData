"""Tests of the recycling table: schema, round trip and the writer thread."""

import sqlite3
from contextlib import closing

from opendofusdata.records import RecyclingEvent
from opendofusdata.recycling_store import recycling_events
from opendofusdata.storage import PriceStore, StoreWriter

FIRST = RecyclingEvent("Brial", ((310, 100), (15073, 10)), 2, "2026-11-11T19:13:49Z")
SECOND = RecyclingEvent("Brial", ((310, 1000),), 3, "2026-11-11T19:18:30Z")


def test_the_table_is_created_with_the_other_tables(tmp_path) -> None:
    PriceStore(str(tmp_path / "r.db")).close()
    with closing(sqlite3.connect(tmp_path / "r.db")) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"recycling_events", "pet_feedings"} <= tables


def test_an_older_database_gets_the_tables_without_losing_data(tmp_path) -> None:
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        connection.execute("CREATE TABLE lot_prices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, "
                           "server TEXT NOT NULL, lot_size INTEGER NOT NULL, price INTEGER NOT NULL, "
                           "captured_at TEXT NOT NULL)")
        connection.execute("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at) "
                           "VALUES (307, 'Brial', 1, 750, 'x')")
        connection.commit()
    store = PriceStore(str(tmp_path / "old.db"))
    try:
        assert len(store.latest_prices()) == 1
        assert recycling_events(store.connection) == []
    finally:
        store.close()


def test_events_round_trip_oldest_first_with_tuple_items(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "r.db"))
    try:
        store.save_record(SECOND)
        store.save_record(FIRST)
        assert recycling_events(store.connection) == [FIRST, SECOND]
        assert isinstance(recycling_events(store.connection)[0].items[0], tuple)
    finally:
        store.close()


def test_the_writer_thread_saves_recycling_events(tmp_path) -> None:
    writer = StoreWriter(str(tmp_path / "r.db"))
    writer.submit(FIRST)
    writer.stop()
    store = PriceStore(str(tmp_path / "r.db"))
    try:
        assert recycling_events(store.connection) == [FIRST]
    finally:
        store.close()
