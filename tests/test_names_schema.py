"""Schema of the item-name table and the named views."""

import sqlite3
from contextlib import closing
from pathlib import Path

from dofus_prices.records import LotPrice, MarketStats
from dofus_prices.storage import PriceStore

OLD_SCHEMA = (
    """CREATE TABLE lot_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, server TEXT NOT NULL,
        lot_size INTEGER NOT NULL, price INTEGER NOT NULL, captured_at TEXT NOT NULL)""",
    """CREATE TABLE market_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, server TEXT NOT NULL,
        period TEXT NOT NULL, points_json TEXT NOT NULL, median INTEGER NOT NULL,
        mean INTEGER NOT NULL, sold_count INTEGER NOT NULL, server_updated_at TEXT NOT NULL,
        last_purchase_at TEXT NOT NULL, captured_at TEXT NOT NULL)""",
)


def names_of(path: Path, kind: str) -> set[str]:
    with closing(sqlite3.connect(path)) as connection, connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
        return {row[0] for row in rows}


def fill(path: Path) -> None:
    store = PriceStore(str(path))
    store.save_lot_price(LotPrice(10, "S", 1, 100, "2026-11-01T00:00:00Z"))
    store.save_lot_price(LotPrice(10, "S", 10, 900, "2026-11-03T00:00:00Z"))
    store.save_lot_price(LotPrice(20, "S", 1, 5, "2026-11-02T00:00:00Z"))
    store.save_market_stats(MarketStats(20, "S", "24h", [(1, 2, 3)], 4, 5, 6, "u", "p", "2026-11-05T00:00:00Z"))
    store.save_market_stats(MarketStats(30, "S", "24h", [], 4, 5, 6, "u", "p", "2026-11-04T00:00:00Z"))
    store.close()


def query(path: Path, sql: str) -> list[tuple]:
    with closing(sqlite3.connect(path)) as connection, connection:
        return connection.execute(sql).fetchall()


def test_fresh_database_gets_the_table_and_the_views(tmp_path: Path) -> None:
    PriceStore(str(tmp_path / "p.db")).close()
    assert "items" in names_of(tmp_path / "p.db", "table")
    assert {"lot_prices_named", "market_stats_named", "unknown_items"} <= names_of(tmp_path / "p.db", "view")


def test_database_from_the_previous_schema_gains_them_and_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        for statement in OLD_SCHEMA:
            connection.execute(statement)
        connection.execute("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at)"
                           " VALUES (1, 'S', 1, 9, 'x')")
    PriceStore(str(path)).close()
    assert "items" in names_of(path, "table")
    assert query(path, "SELECT item_id, item_name FROM lot_prices_named") == [(1, "N/A")]


def test_views_give_na_for_unknown_ids_and_the_name_otherwise(tmp_path: Path) -> None:
    path = tmp_path / "p.db"
    fill(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO items VALUES (10, 'Chose', 12, 'Type')")
    rows = query(path, "SELECT item_id, item_name, item_level, item_type FROM lot_prices_named ORDER BY id")
    assert rows == [(10, "Chose", 12, "Type"), (10, "Chose", 12, "Type"), (20, "N/A", None, None)]
    stats = query(path, "SELECT item_id, item_name, period FROM market_stats_named ORDER BY item_id")
    assert stats == [(20, "N/A", "24h"), (30, "N/A", "24h")]
    columns = [row[1] for row in query(path, "PRAGMA table_info(market_stats_named)")]
    assert "points_json" not in columns and {"median", "item_name", "captured_at"} <= set(columns)


def test_unknown_items_counts_and_first_last_seen(tmp_path: Path) -> None:
    path = tmp_path / "p.db"
    fill(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO items VALUES (10, 'Chose', NULL, '')")
    assert query(path, "SELECT * FROM unknown_items") == [
        (20, 1, 1, "2026-11-02T00:00:00Z", "2026-11-05T00:00:00Z"),
        (30, 0, 1, "2026-11-04T00:00:00Z", "2026-11-04T00:00:00Z"),
    ]
