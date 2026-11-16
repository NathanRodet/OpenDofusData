"""What the synchronisation has moved so far, counted in the local database (shown under the key)."""

import logging
import sqlite3
from pathlib import Path
from typing import NamedTuple

from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE
from opendofusdata.sync_store import SKIPPED

logger = logging.getLogger(__name__)
COUNTS_SQL = f"""
    SELECT
      COALESCE(SUM(origin = '{ORIGIN_LOCAL}' AND synced_at IS NOT NULL AND synced_at != '{SKIPPED}'), 0),
      COALESCE(SUM(origin = '{ORIGIN_LOCAL}' AND (synced_at IS NULL OR synced_at != '{SKIPPED}')), 0),
      COALESCE(SUM(origin = '{ORIGIN_REMOTE}'), 0)
    FROM lot_prices"""
COUNTS_TEXT = "Envoyés : {sent}/{to_send}. Reçus des autres joueurs : {received}."


class SyncCounts(NamedTuple):
    """Rows sent out of the local rows worth sending, and rows received from other players."""

    sent: int
    to_send: int
    received: int


def count_sync(connection: sqlite3.Connection) -> SyncCounts:
    """Count the readings sent and received so far."""
    return SyncCounts(*connection.execute(COUNTS_SQL).fetchone())


def counts_text(counts: SyncCounts) -> str:
    """The line shown to the player."""
    return COUNTS_TEXT.format(sent=counts.sent, to_send=counts.to_send, received=counts.received)


def read_counts_text(database_path: str) -> str:
    """The counters line read from a database file, or an empty text when it cannot be read."""
    try:
        connection = sqlite3.connect(f"{Path(database_path).resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:  # a missing or busy database only hides the line
        logger.warning("compteurs de synchronisation illisibles : %s", error)
        return ""
    try:
        return counts_text(count_sync(connection))
    except sqlite3.Error as error:
        logger.warning("compteurs de synchronisation illisibles : %s", error)
        return ""
    finally:
        connection.close()
