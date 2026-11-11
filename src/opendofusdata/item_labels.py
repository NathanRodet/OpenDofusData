"""Item names read from the database `items` table, for the read commands."""

import logging
import sqlite3
from collections.abc import Callable

logger = logging.getLogger(__name__)

UNKNOWN_ITEM_NAME = "N/A"
ITEM_NAMES_SQL = "SELECT item_id, name_fr FROM items"
ItemLabeler = Callable[[int], str]


def load_item_labeler(connection: sqlite3.Connection) -> ItemLabeler:
    """Return a function id -> French name, 'N/A' for ids missing from the items table."""
    try:
        names = dict(connection.execute(ITEM_NAMES_SQL).fetchall())
    except sqlite3.OperationalError as error:
        logger.info("table des noms absente, noms affichés N/A (%s)", error)
        names = {}
    return lambda item_id: names.get(item_id, UNKNOWN_ITEM_NAME)
