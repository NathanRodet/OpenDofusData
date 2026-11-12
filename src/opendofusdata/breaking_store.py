"""SQL of the broken objects table: one row per object destroyed at the Concasseur."""

import json
import sqlite3

from opendofusdata.records import BrokenItem

BREAKING_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS broken_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT NOT NULL, captured_at TEXT NOT NULL,
        item_id INTEGER NOT NULL, quantity INTEGER NOT NULL, coefficient REAL NOT NULL,
        runes_json TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_broken_items_time ON broken_items (captured_at, id)",
)
INSERT_BROKEN_SQL = ("INSERT INTO broken_items (server, captured_at, item_id, quantity, coefficient, runes_json) "
                     "VALUES (?, ?, ?, ?, ?, ?)")
SELECT_BROKEN_SQL = ("SELECT server, captured_at, item_id, quantity, coefficient, runes_json FROM broken_items "
                     "ORDER BY captured_at, id")
OLD_TABLE = "breaking_events"
SELECT_OLD_SQL = f"SELECT server, captured_at, items_json FROM {OLD_TABLE} ORDER BY id"


def save_broken_item(connection: sqlite3.Connection, item: BrokenItem) -> None:
    """Append one destroyed object; runes stored as a JSON list of [rune item id, quantity]."""
    connection.execute(INSERT_BROKEN_SQL, (item.server, item.captured_at, item.item_id, item.quantity,
                                           item.coefficient, json.dumps(item.runes)))


def broken_items(connection: sqlite3.Connection) -> list[BrokenItem]:
    """Every stored destroyed object, oldest first."""
    rows = connection.execute(SELECT_BROKEN_SQL)
    return [BrokenItem(server, item_id, quantity, coefficient,
                       tuple((rune, count) for rune, count in json.loads(runes_json)), captured_at)
            for server, captured_at, item_id, quantity, coefficient, runes_json in rows]


def migrate_breaking_batches(connection: sqlite3.Connection) -> None:
    """Split the rows of the old per-batch table into one row per object, then drop the old table."""
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (OLD_TABLE,)).fetchone()
    if exists is None:
        return
    for server, captured_at, items_json in connection.execute(SELECT_OLD_SQL).fetchall():
        for item_id, quantity, coefficient, runes in json.loads(items_json):
            save_broken_item(connection, BrokenItem(server, item_id, quantity, coefficient,
                                                    tuple((rune, count) for rune, count in runes), captured_at))
    connection.execute(f"DROP TABLE {OLD_TABLE}")
