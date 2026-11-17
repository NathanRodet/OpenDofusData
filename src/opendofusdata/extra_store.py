"""The category tables stored beside prices and statistics: schema and per-type save functions."""

import sqlite3
from collections.abc import Callable

from opendofusdata.names_db import ensure_rate_column
from opendofusdata.breaking_store import BREAKING_SCHEMA_STATEMENTS, migrate_breaking_batches, save_broken_item
from opendofusdata.manual_schema import MANUAL_SCHEMA_STATEMENTS
from opendofusdata.pets_store import PETS_SCHEMA_STATEMENTS, save_pet_feeding
from opendofusdata.records import BrokenItem, PetFeeding, Record

EXTRA_SCHEMA_STATEMENTS = (*PETS_SCHEMA_STATEMENTS, *BREAKING_SCHEMA_STATEMENTS, *MANUAL_SCHEMA_STATEMENTS)
# Recycling is no longer collected: its table and view are removed from older databases.
OBSOLETE_STATEMENTS = ("DROP VIEW IF EXISTS recycling_yields", "DROP TABLE IF EXISTS recycling_events")
EXTRA_SAVERS: dict[type, Callable[[sqlite3.Connection, Record], None]] = {
    PetFeeding: save_pet_feeding,
    BrokenItem: save_broken_item,
}


def prepare_extra_tables(connection: sqlite3.Connection) -> None:
    """Create the category tables and bring an older database up to date."""
    for statement in EXTRA_SCHEMA_STATEMENTS:
        connection.execute(statement)
    for statement in OBSOLETE_STATEMENTS:
        connection.execute(statement)
    migrate_breaking_batches(connection)
    ensure_rate_column(connection)
