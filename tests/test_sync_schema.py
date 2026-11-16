"""The synchronisation columns of lot_prices and the sync state table (migration of older databases)."""

import sqlite3

import pytest

from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore
from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE, prepare_sync_schema

OLD_LOT_PRICES = """CREATE TABLE lot_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, server TEXT NOT NULL,
    lot_size INTEGER NOT NULL, price INTEGER NOT NULL, captured_at TEXT NOT NULL)"""
INSERT_REMOTE = ("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at, origin, source_key_id) "
                 "VALUES (?, 'Brial', 1, ?, '2026-11-16T10:00:00Z', 'remote', ?)")


@pytest.fixture
def connection() -> sqlite3.Connection:
    opened = sqlite3.connect(":memory:")
    opened.execute(OLD_LOT_PRICES)
    return opened


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def test_origins_are_local_and_remote() -> None:
    assert (ORIGIN_LOCAL, ORIGIN_REMOTE) == ("local", "remote")


def test_columns_and_state_table_are_created(connection: sqlite3.Connection) -> None:
    prepare_sync_schema(connection)
    assert {"origin", "synced_at", "source_key_id"} <= set(columns(connection, "lot_prices"))
    assert columns(connection, "sync_state") == ["name", "value"]


def test_migration_keeps_existing_rows_as_local_and_unsent(connection: sqlite3.Connection) -> None:
    connection.execute("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at) "
                       "VALUES (1, 'Brial', 1, 100, '2026-11-16T09:00:00Z')")
    prepare_sync_schema(connection)
    assert connection.execute("SELECT item_id, price, origin, synced_at, source_key_id FROM lot_prices").fetchall() == [
        (1, 100, "local", None, None)]


def test_preparing_twice_changes_nothing(connection: sqlite3.Connection) -> None:
    prepare_sync_schema(connection)
    before = columns(connection, "lot_prices")
    prepare_sync_schema(connection)
    assert columns(connection, "lot_prices") == before


def test_remote_duplicates_are_refused_by_the_unique_index(connection: sqlite3.Connection) -> None:
    prepare_sync_schema(connection)
    connection.execute(INSERT_REMOTE, (1, 100, "BBBBBBBBBBB"))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(INSERT_REMOTE, (1, 100, "BBBBBBBBBBB"))


def test_same_reading_from_two_other_keys_is_kept_twice(connection: sqlite3.Connection) -> None:
    prepare_sync_schema(connection)
    connection.execute(INSERT_REMOTE, (1, 100, "BBBBBBBBBBB"))
    connection.execute(INSERT_REMOTE, (1, 100, "CCCCCCCCCCC"))
    assert connection.execute("SELECT COUNT(*) FROM lot_prices").fetchone() == (2,)


def test_local_duplicates_are_not_constrained(connection: sqlite3.Connection) -> None:
    prepare_sync_schema(connection)
    for _ in range(2):
        connection.execute("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at) "
                           "VALUES (1, 'Brial', 1, 100, '2026-11-16T10:00:00Z')")
    assert connection.execute("SELECT COUNT(*) FROM lot_prices").fetchone() == (2,)


def test_price_store_creates_the_sync_columns() -> None:
    store = PriceStore(":memory:")
    assert {"origin", "synced_at", "source_key_id"} <= set(columns(store.connection, "lot_prices"))
    assert "sync_state" in {row[0] for row in store.connection.execute("SELECT name FROM sqlite_master")}
    store.close()


def test_existing_price_queries_return_the_same_columns() -> None:
    store = PriceStore(":memory:")
    lot = LotPrice(7, "Brial", 10, 750, "2026-11-16T10:00:00Z")
    store.save_lot_price(lot)
    assert store.latest_prices(7) == [lot]
    assert store.price_history(7, 10) == [lot]
    store.close()
