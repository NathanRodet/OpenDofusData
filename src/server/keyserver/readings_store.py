"""The journal of price readings sent by the players, kept in SQLite for a few days."""

import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from keyserver.event_store import EventStore
from keyserver.schemas import OBSERVATION_RETENTION_DAYS, Reading

RETENTION_DAYS = OBSERVATION_RETENTION_DAYS
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS readings (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL, server TEXT NOT NULL, item_id INTEGER NOT NULL,
        lot_size INTEGER NOT NULL, price INTEGER NOT NULL, observed_at INTEGER NOT NULL)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_readings_natural
        ON readings (key_id, server, item_id, lot_size, observed_at)""",
    "CREATE INDEX IF NOT EXISTS idx_readings_key ON readings (key_id)",
    "CREATE INDEX IF NOT EXISTS idx_readings_observed ON readings (observed_at)",
)
INSERT_SQL = ("INSERT OR IGNORE INTO readings (key_id, server, item_id, lot_size, price, observed_at) "
              "VALUES (?, ?, ?, ?, ?, ?)")
COLUMNS = "seq, key_id, server, item_id, lot_size, price, observed_at"
CHANGES_SQL = (f"SELECT {COLUMNS} FROM readings WHERE key_id != ? AND seq > ? ORDER BY seq LIMIT ?")
OWN_SQL = f"SELECT {COLUMNS} FROM readings WHERE key_id = ? AND seq > ? ORDER BY seq LIMIT ?"
LATEST_SQL = f"""
    SELECT {COLUMNS} FROM (
        SELECT {COLUMNS}, ROW_NUMBER() OVER (
            PARTITION BY server, item_id, lot_size ORDER BY observed_at DESC, seq DESC) AS rank
        FROM readings WHERE key_id != ?)
    WHERE rank = 1 AND seq > ? ORDER BY seq LIMIT ?"""


class StoredReading(NamedTuple):
    """A reading as the players receive it: order number, sender key id, price data and UTC date."""

    seq: int
    key_id: str
    server: str
    item_id: int
    lot_size: int
    price: int
    observed_at: str


def _stored(row: tuple) -> StoredReading:
    moment = datetime.fromtimestamp(row[6], timezone.utc).strftime(ISO_FORMAT)
    return StoredReading(*row[:6], moment)


class ReadingStore:
    """Readings of all the keys; safe to share between the threads of the web server."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        with self._lock, self._connection:
            for statement in SCHEMA_STATEMENTS:
                self._connection.execute(statement)
        self.events = EventStore(connection, self._lock)  # breakings and pet upgrades live in the same file

    def add_batch(self, key_id: str, readings: Sequence[Reading]) -> tuple[int, int]:
        """Store the readings of one key; returns (accepted, duplicates). Known readings are ignored."""
        accepted = 0
        with self._lock, self._connection:
            for item in readings:
                cursor = self._connection.execute(INSERT_SQL, (
                    key_id, item.server, item.item_id, item.lot_size, item.price, int(item.observed_at.timestamp())))
                accepted += cursor.rowcount
        return accepted, len(readings) - accepted

    def changes_since(self, key_id: str, since: int, limit: int) -> list[StoredReading]:
        """Readings of the other keys that arrived after order number `since`, oldest arrival first."""
        with self._lock:
            return [_stored(row) for row in self._connection.execute(CHANGES_SQL, (key_id, since, limit))]

    def latest_page(self, key_id: str, after: int, limit: int) -> list[StoredReading]:
        """The newest reading of each (server, item, lot) among the other keys, after order number `after`."""
        with self._lock:
            return [_stored(row) for row in self._connection.execute(LATEST_SQL, (key_id, after, limit))]

    def own_page(self, key_id: str, after: int, limit: int) -> list[StoredReading]:
        """The readings this key sent itself after order number `after` (a player restoring their own history)."""
        with self._lock:
            return [_stored(row) for row in self._connection.execute(OWN_SQL, (key_id, after, limit))]

    def highest_seq(self) -> int:
        """The order number of the last stored reading (0 when empty)."""
        with self._lock:
            return self._connection.execute("SELECT COALESCE(MAX(seq), 0) FROM readings").fetchone()[0]

    def purge_older_than(self, cutoff: datetime) -> int:
        """Delete the readings and events observed before the cutoff; returns how many."""
        with self._lock, self._connection:
            old = self._connection.execute(
                "DELETE FROM readings WHERE observed_at < ?", (int(cutoff.timestamp()),)).rowcount
        return old + self.events.purge_older_than(cutoff)

    def purge_key(self, key_id: str) -> int:
        """Delete every reading and event sent by this key; returns how many."""
        with self._lock, self._connection:
            own = self._connection.execute("DELETE FROM readings WHERE key_id = ?", (key_id,)).rowcount
        return own + self.events.purge_key(key_id)

    def close(self) -> None:
        """Close the database file."""
        with self._lock:
            self._connection.close()


def open_readings(path: Path | str) -> ReadingStore:
    """Open (and create when needed) the readings journal stored in this SQLite file."""
    return ReadingStore(sqlite3.connect(path, check_same_thread=False))
