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


EVENT_TABLES = ("broken_items", "pet_feedings")  # breakings and pet upgrades are shared like the prices
EVENT_STATEMENTS = (
    f"""CREATE INDEX IF NOT EXISTS idx_broken_items_unsent ON broken_items (id)
        WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL""",
    f"""CREATE UNIQUE INDEX IF NOT EXISTS idx_broken_items_remote
        ON broken_items (server, item_id, captured_at, quantity, runes_json, source_key_id)
        WHERE origin = '{ORIGIN_REMOTE}'""",
    f"""CREATE INDEX IF NOT EXISTS idx_pet_feedings_unsent ON pet_feedings (id)
        WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL""",
    f"""CREATE UNIQUE INDEX IF NOT EXISTS idx_pet_feedings_remote
        ON pet_feedings (server, pet_item_id, captured_at, resources_json, source_key_id)
        WHERE origin = '{ORIGIN_REMOTE}'""",
)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _add_sync_columns(connection: sqlite3.Connection, table: str) -> None:
    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    for name, definition in NEW_COLUMNS:
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def prepare_sync_schema(connection: sqlite3.Connection) -> None:
    """Add the sync columns, indexes and state table; running it again changes nothing.

    The event tables are prepared only when they exist (a bare test database may hold prices alone).
    """
    tables = _table_names(connection)
    present = [table for table in ("lot_prices", *EVENT_TABLES) if table in tables]
    for table in present:
        _add_sync_columns(connection, table)
    events_ready = all(table in tables for table in EVENT_TABLES)
    for statement in (*SYNC_STATEMENTS, *(EVENT_STATEMENTS if events_ready else ())):
        connection.execute(statement)
