"""SQL of the breaking events table (schema, save and read helpers)."""

import json
import sqlite3

from opendofusdata.records import BreakingEvent, BrokenItem

BREAKING_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS breaking_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT NOT NULL, captured_at TEXT NOT NULL,
        items_json TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_breaking_events_time ON breaking_events (captured_at, id)",
)
INSERT_BREAKING_SQL = "INSERT INTO breaking_events (server, captured_at, items_json) VALUES (?, ?, ?)"
SELECT_BREAKING_SQL = "SELECT server, captured_at, items_json FROM breaking_events ORDER BY captured_at, id"


def save_breaking_event(connection: sqlite3.Connection, event: BreakingEvent) -> None:
    """Append one breaking; items stored as [item id, quantity, coefficient, [[rune id, quantity]...]]."""
    items = [[item.item_id, item.quantity, item.coefficient, item.runes] for item in event.items]
    connection.execute(INSERT_BREAKING_SQL, (event.server, event.captured_at, json.dumps(items)))


def breaking_events(connection: sqlite3.Connection) -> list[BreakingEvent]:
    """Every stored breaking, oldest first."""
    events = []
    for server, captured_at, items_json in connection.execute(SELECT_BREAKING_SQL):
        items = tuple(BrokenItem(item_id, quantity, coefficient, tuple((rune, count) for rune, count in runes))
                      for item_id, quantity, coefficient, runes in json.loads(items_json))
        events.append(BreakingEvent(server, items, captured_at))
    return events
