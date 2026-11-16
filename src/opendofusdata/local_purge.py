"""The optional purge of the local database: readings older than seven days go, the latest of each key stays.

Only `lot_prices` and `market_stats` are touched. Favorites and manual pet observations live in the config file,
and names, servers, breakings, pet upgrades and the sync state are other tables: none of them is ever purged.
"""

import logging
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from opendofusdata.purge_options import purge_enabled

logger = logging.getLogger(__name__)

LOCAL_RETENTION_DAYS = 7
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
BUSY_TIMEOUT_SECONDS = 30.0
PURGE_SQL = """
    DELETE FROM {table} WHERE captured_at < :cutoff AND id NOT IN (
        SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY {key} ORDER BY captured_at DESC, id DESC) AS rank
            FROM {table}) WHERE rank = 1)"""
LOT_KEY = "item_id, server, lot_size"
STATS_KEY = "item_id, server, period"
Clock = Callable[[], datetime]


class PurgeResult(NamedTuple):
    """How many rows were deleted from each table."""

    lot_prices: int
    market_stats: int


def _purge_table(connection: sqlite3.Connection, table: str, key: str, cutoff: str) -> int:
    return connection.execute(PURGE_SQL.format(table=table, key=key), {"cutoff": cutoff}).rowcount


def purge_old_readings(connection: sqlite3.Connection, now: datetime) -> PurgeResult:
    """Delete the price and statistics rows older than seven days, except the latest row of each key."""
    cutoff = (now - timedelta(days=LOCAL_RETENTION_DAYS)).strftime(DATE_FORMAT)
    with connection:
        lots = _purge_table(connection, "lot_prices", LOT_KEY, cutoff)
        stats = _purge_table(connection, "market_stats", STATS_KEY, cutoff)
    return PurgeResult(lots, stats)


def purge_database_file(database_path: str, clock: Clock = lambda: datetime.now(timezone.utc)) -> PurgeResult:
    """Open the database file, purge it and close it again."""
    with closing(sqlite3.connect(database_path, timeout=BUSY_TIMEOUT_SECONDS)) as connection:
        return purge_old_readings(connection, clock())


def startup_purge(config: Mapping[str, object], database_path: str,
                  clock: Clock = lambda: datetime.now(timezone.utc)) -> PurgeResult | None:
    """Purge at startup when the player switched the setting on; None when it is off or cannot run.

    A missing database is never created here, and a database that is locked or not prepared yet is only logged.
    """
    if not purge_enabled(config) or not Path(database_path).is_file():
        return None
    try:
        return purge_database_file(database_path, clock)
    except sqlite3.Error as error:
        logger.warning("purge locale au lancement impossible (%s : %s)", database_path, error)
        return None
