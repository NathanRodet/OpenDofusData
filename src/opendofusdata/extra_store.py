"""The category tables stored beside prices and statistics: schema and per-type save functions."""

import sqlite3
from collections.abc import Callable

from opendofusdata.breaking_store import BREAKING_SCHEMA_STATEMENTS, migrate_breaking_batches, save_broken_item
from opendofusdata.pets_store import PETS_SCHEMA_STATEMENTS, save_pet_feeding
from opendofusdata.records import BrokenItem, PetFeeding, Record, RecyclingEvent
from opendofusdata.recycling_store import RECYCLING_SCHEMA_STATEMENTS, save_recycling_event

EXTRA_SCHEMA_STATEMENTS = (*RECYCLING_SCHEMA_STATEMENTS, *PETS_SCHEMA_STATEMENTS, *BREAKING_SCHEMA_STATEMENTS)
EXTRA_SAVERS: dict[type, Callable[[sqlite3.Connection, Record], None]] = {
    RecyclingEvent: save_recycling_event,
    PetFeeding: save_pet_feeding,
    BrokenItem: save_broken_item,
}


def prepare_extra_tables(connection: sqlite3.Connection) -> None:
    """Create the category tables and bring an older database up to date."""
    for statement in EXTRA_SCHEMA_STATEMENTS:
        connection.execute(statement)
    migrate_breaking_batches(connection)
