"""Item names read from the database `items` table, for the read commands."""

import logging
import sqlite3
from collections.abc import Callable

logger = logging.getLogger(__name__)

UNKNOWN_ITEM_NAME = "N/A"
UNKNOWN_ITEM_TYPE = "N/A"
ITEM_LABELS_SQL = "SELECT item_id, name_fr, type_fr FROM items"
ItemLabeler = Callable[[int], str]
ItemTyper = Callable[[int], str]


def load_item_labelers(connection: sqlite3.Connection) -> tuple[ItemLabeler, ItemTyper]:
    """Return (id -> French name, id -> item category); 'N/A' for ids missing from items."""
    try:
        rows = connection.execute(ITEM_LABELS_SQL).fetchall()
    except sqlite3.OperationalError as error:
        logger.info("table des noms absente, noms affichés N/A (%s)", error)
        rows = []
    names = {item_id: name for item_id, name, _ in rows}
    types = {item_id: type_name or UNKNOWN_ITEM_TYPE for item_id, _, type_name in rows}
    return (lambda item_id: names.get(item_id, UNKNOWN_ITEM_NAME),
            lambda item_id: types.get(item_id, UNKNOWN_ITEM_TYPE))
