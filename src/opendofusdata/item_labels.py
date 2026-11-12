"""Item names read from the database `items` table, for the read commands."""

import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

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


def read_only_uri(path: str) -> str:
    """The SQLite URI that opens an existing database file read-only."""
    return Path(path).resolve().as_uri() + "?mode=ro"


def item_labeler_for_database(path: str) -> ItemLabeler:
    """Name lookup read from a database file; 'N/A' when it is absent or unreadable (never creates it)."""
    if not Path(path).is_file():
        return lambda item_id: UNKNOWN_ITEM_NAME
    try:
        with closing(sqlite3.connect(read_only_uri(path), uri=True)) as connection:
            return load_item_labelers(connection)[0]
    except sqlite3.Error as error:
        logger.warning("noms d'objets illisibles dans %s (%s)", path, error)
        return lambda item_id: UNKNOWN_ITEM_NAME
