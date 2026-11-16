"""The retention of the readings journal: old readings are deleted once a day."""

import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from keyserver.readings_store import RETENTION_DAYS, ReadingStore

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 86_400
PURGE_RETRY_SECONDS = 300  # after a failed purge the next attempt comes soon, not a day later


def purge_expired(readings: ReadingStore, now: datetime) -> int:
    """Delete the readings observed more than RETENTION_DAYS before `now`; returns how many."""
    return readings.purge_older_than(now - timedelta(days=RETENTION_DAYS))


def _purge_once(readings: ReadingStore) -> bool:
    """One purge; any failure is logged with its traceback and reported, never raised: retention must not stop."""
    try:
        deleted = purge_expired(readings, datetime.now(timezone.utc))
    except sqlite3.Error:  # the expected one: database locked or closed
        logger.exception("purge de rétention échouée, nouvelle tentative bientôt")
        return False
    except Exception:  # a bug must be visible in the log but must not end the loop
        logger.exception("purge de rétention: erreur inattendue, nouvelle tentative bientôt")
        return False
    logger.info("purge de rétention : %d relevé(s) supprimé(s)", deleted)
    return True


def start_purge_loop(readings: ReadingStore, interval_seconds: float = PURGE_INTERVAL_SECONDS,
                     retry_seconds: float = PURGE_RETRY_SECONDS) -> threading.Event:
    """Purge now, then every interval (sooner after a failure), in a daemon thread. Setting the event stops it."""
    stop = threading.Event()

    def loop() -> None:
        succeeded = _purge_once(readings)
        while not stop.wait(interval_seconds if succeeded else min(retry_seconds, interval_seconds)):
            succeeded = _purge_once(readings)

    threading.Thread(target=loop, name="retention-purge", daemon=True).start()
    return stop
