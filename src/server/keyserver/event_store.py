"""The journal of shared events (breakings, pet upgrades): one table, a kind per row, kept a few days."""

import json
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NamedTuple

from pydantic import BaseModel

from keyserver.event_schemas import payload_text

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, key_id TEXT NOT NULL,
        observed_at INTEGER NOT NULL, payload TEXT NOT NULL)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_natural ON events (kind, key_id, observed_at, payload)",
    "CREATE INDEX IF NOT EXISTS idx_events_key ON events (key_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_observed ON events (observed_at)",
)
INSERT_SQL = "INSERT OR IGNORE INTO events (kind, key_id, observed_at, payload) VALUES (?, ?, ?, ?)"
COLUMNS = "seq, key_id, observed_at, payload"
CHANGES_SQL = f"SELECT {COLUMNS} FROM events WHERE kind = ? AND key_id != ? AND seq > ? ORDER BY seq LIMIT ?"
OWN_SQL = f"SELECT {COLUMNS} FROM events WHERE kind = ? AND key_id = ? AND seq > ? ORDER BY seq LIMIT ?"


class StoredEvent(NamedTuple):
    """An event as the players receive it: order number, sender key id, UTC date and the event's own fields."""

    seq: int
    key_id: str
    observed_at: str
    payload: dict[str, object]

    def view(self) -> dict[str, object]:
        """The flat object sent to the players (the key id is a pseudonym, never the key itself)."""
        return {"seq": self.seq, "key_id": self.key_id, "observed_at": self.observed_at, **self.payload}


def _stored(row: tuple) -> StoredEvent:
    moment = datetime.fromtimestamp(row[2], timezone.utc).strftime(ISO_FORMAT)
    return StoredEvent(row[0], row[1], moment, json.loads(row[3]))


class EventStore:
    """Events of all the keys; shares the connection and the lock of the readings journal."""

    def __init__(self, connection: sqlite3.Connection, lock: threading.Lock) -> None:
        self._connection, self._lock = connection, lock
        with self._lock, self._connection:
            for statement in SCHEMA_STATEMENTS:
                self._connection.execute(statement)

    def add_batch(self, kind: str, key_id: str, events: Sequence[BaseModel]) -> tuple[int, int]:
        """Store the events of one key; returns (accepted, duplicates). Known events are ignored."""
        accepted = 0
        with self._lock, self._connection:
            for event in events:
                moment = int(event.observed_at.timestamp())  # type: ignore[attr-defined]
                accepted += self._connection.execute(INSERT_SQL, (kind, key_id, moment, payload_text(event))).rowcount
        return accepted, len(events) - accepted

    def changes_since(self, kind: str, key_id: str, since: int, limit: int) -> list[StoredEvent]:
        """Events of the other keys that arrived after order number `since`, oldest arrival first."""
        with self._lock:
            return [_stored(row) for row in self._connection.execute(CHANGES_SQL, (kind, key_id, since, limit))]

    def own_page(self, kind: str, key_id: str, after: int, limit: int) -> list[StoredEvent]:
        """The events this key sent itself after order number `after` (restoring a player's own history)."""
        with self._lock:
            return [_stored(row) for row in self._connection.execute(OWN_SQL, (kind, key_id, after, limit))]

    def purge_older_than(self, cutoff: datetime) -> int:
        """Delete the events observed before the cutoff; returns how many."""
        with self._lock, self._connection:
            return self._connection.execute("DELETE FROM events WHERE observed_at < ?",
                                            (int(cutoff.timestamp()),)).rowcount

    def purge_key(self, key_id: str) -> int:
        """Delete every event sent by this key; returns how many."""
        with self._lock, self._connection:
            return self._connection.execute("DELETE FROM events WHERE key_id = ?", (key_id,)).rowcount
