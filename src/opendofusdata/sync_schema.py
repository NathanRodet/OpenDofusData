"""The synchronisation columns of lot_prices and the sync state table (older databases are migrated in place)."""

import sqlite3

ORIGIN_LOCAL = "local"
ORIGIN_REMOTE = "remote"
NEW_COLUMNS = (
    ("origin", f"TEXT NOT NULL DEFAULT '{ORIGIN_LOCAL}'"),
    ("synced_at", "TEXT"),
    ("source_key_id", "TEXT"),
)
SYNC_STATEMENTS = (
    f"""CREATE INDEX IF NOT EXISTS idx_lot_prices_unsent ON lot_prices (id)
        WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL""",
    f"""CREATE UNIQUE INDEX IF NOT EXISTS idx_lot_prices_remote
        ON lot_prices (item_id, server, lot_size, captured_at, source_key_id) WHERE origin = '{ORIGIN_REMOTE}'""",
    "CREATE TABLE IF NOT EXISTS sync_state (name TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


def prepare_sync_schema(connection: sqlite3.Connection) -> None:
    """Add the sync columns, indexes and state table; running it again changes nothing."""
    existing = {row[1] for row in connection.execute("PRAGMA table_info(lot_prices)")}
    for name, definition in NEW_COLUMNS:
        if name not in existing:
            connection.execute(f"ALTER TABLE lot_prices ADD COLUMN {name} {definition}")
    for statement in SYNC_STATEMENTS:
        connection.execute(statement)
