"""SQL of the recycling events table (schema, insert and read helpers)."""

import json
import sqlite3

from opendofusdata.records import RecyclingEvent
from opendofusdata.recycling import PERSONAL_FACTOR

RECYCLING_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS recycling_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT NOT NULL, captured_at TEXT NOT NULL,
        nuggets INTEGER NOT NULL, items_json TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_recycling_events_time ON recycling_events (captured_at, id)",
    # Each recycling next to the yield the game announced for it (an item without a known rate counts as 0).
    f"""CREATE VIEW IF NOT EXISTS recycling_yields AS
        SELECT event.id, event.server, event.captured_at, event.nuggets AS obtained,
               ROUND({PERSONAL_FACTOR} * SUM(json_extract(entry.value, '$[1]')
                     * COALESCE(item.recycling_nuggets, 0)), 4) AS expected
        FROM recycling_events AS event
        JOIN json_each(event.items_json) AS entry
        LEFT JOIN items AS item ON item.item_id = json_extract(entry.value, '$[0]')
        GROUP BY event.id""",
)
INSERT_RECYCLING_SQL = ("INSERT INTO recycling_events (server, captured_at, nuggets, items_json) "
                        "VALUES (?, ?, ?, ?)")
SELECT_RECYCLING_SQL = ("SELECT server, captured_at, nuggets, items_json FROM recycling_events "
                        "ORDER BY captured_at, id")


def recycling_values(event: RecyclingEvent) -> tuple:
    """The INSERT parameters of an event (items stored as a JSON list of [item id, quantity])."""
    return event.server, event.captured_at, event.nuggets, json.dumps(event.items)


def recycling_from_row(row: tuple) -> RecyclingEvent:
    """Rebuild an event from a SELECT_RECYCLING_SQL row."""
    server, captured_at, nuggets, items_json = row
    items = tuple((item_id, quantity) for item_id, quantity in json.loads(items_json))
    return RecyclingEvent(server, items, nuggets, captured_at)


def save_recycling_event(connection: sqlite3.Connection, event: RecyclingEvent) -> None:
    """Append one recycling (the items of the window and the nuggets obtained)."""
    connection.execute(INSERT_RECYCLING_SQL, recycling_values(event))


def recycling_events(connection: sqlite3.Connection) -> list[RecyclingEvent]:
    """Every stored recycling, oldest first."""
    return [recycling_from_row(row) for row in connection.execute(SELECT_RECYCLING_SQL)]
