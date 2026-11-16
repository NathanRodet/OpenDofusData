"""The list of revoked key identifiers, kept in SQLite."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

CREATE_TABLE_SQL = "CREATE TABLE IF NOT EXISTS revoked_keys (key_id TEXT PRIMARY KEY, revoked_at TEXT NOT NULL)"
INSERT_SQL = "INSERT OR IGNORE INTO revoked_keys (key_id, revoked_at) VALUES (?, ?)"
SELECT_SQL = "SELECT 1 FROM revoked_keys WHERE key_id = ?"


class RevocationStore:
    """Revoked key ids; safe to share between the threads of the web server."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        with self._lock, self._connection:
            self._connection.execute(CREATE_TABLE_SQL)

    def revoke(self, key_id: str) -> None:
        """Revoke the key; revoking twice changes nothing."""
        moment = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(INSERT_SQL, (key_id, moment))

    def close(self) -> None:
        """Close the database file."""
        with self._lock:
            self._connection.close()

    def is_revoked(self, key_id: str) -> bool:
        """True when this identifier has been revoked."""
        with self._lock:
            return self._connection.execute(SELECT_SQL, (key_id,)).fetchone() is not None


def open_revocations(path: Path | str) -> RevocationStore:
    """Open (and create when needed) the revocation list stored in this SQLite file."""
    return RevocationStore(sqlite3.connect(path, check_same_thread=False))
