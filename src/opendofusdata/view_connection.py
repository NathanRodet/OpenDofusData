"""Read-only access to the price database for the views."""

import logging
import sqlite3
from pathlib import Path

from opendofusdata.item_labels import read_only_uri

logger = logging.getLogger(__name__)

READ_TIMEOUT_SECONDS = 1.0
_reported_missing: set[str] = set()


def open_view_connection(path: str) -> sqlite3.Connection | None:
    """Open the database read-only; None (and one warning) when the file is missing or unreadable."""
    if not Path(path).is_file():
        if path not in _reported_missing:
            _reported_missing.add(path)
            logger.warning("base de données absente : %s", path)
        return None
    _reported_missing.discard(path)
    try:
        return sqlite3.connect(read_only_uri(path), uri=True, timeout=READ_TIMEOUT_SECONDS)
    except sqlite3.Error as error:
        logger.warning("base de données illisible : %s (%s)", path, error)
        return None
