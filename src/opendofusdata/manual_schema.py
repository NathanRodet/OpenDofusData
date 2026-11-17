"""The table of the typed experience: every change is a snapshot of the totals of one resource (shared like events)."""

import sqlite3

MANUAL_TABLE = "pet_manual_entries"
MANUAL_SCHEMA_STATEMENTS = (
    f"""CREATE TABLE IF NOT EXISTS {MANUAL_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL, item_id INTEGER NOT NULL,
        units INTEGER NOT NULL, experience INTEGER NOT NULL)""",
    f"CREATE INDEX IF NOT EXISTS idx_{MANUAL_TABLE}_item ON {MANUAL_TABLE} (item_id, captured_at, id)",
)


def prepare_manual_table(connection: sqlite3.Connection) -> None:
    """Create the table when it is missing."""
    for statement in MANUAL_SCHEMA_STATEMENTS:
        connection.execute(statement)
