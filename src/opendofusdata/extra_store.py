"""The category tables stored beside prices and statistics: schema and per-type save functions."""

import sqlite3
from collections.abc import Callable

from opendofusdata.breaking_store import BREAKING_SCHEMA_STATEMENTS, save_breaking_event
from opendofusdata.pets_store import PETS_SCHEMA_STATEMENTS, save_pet_feeding
from opendofusdata.records import BreakingEvent, PetFeeding, Record, RecyclingEvent
from opendofusdata.recycling_store import RECYCLING_SCHEMA_STATEMENTS, save_recycling_event

EXTRA_SCHEMA_STATEMENTS = (*RECYCLING_SCHEMA_STATEMENTS, *PETS_SCHEMA_STATEMENTS, *BREAKING_SCHEMA_STATEMENTS)
EXTRA_SAVERS: dict[type, Callable[[sqlite3.Connection, Record], None]] = {
    RecyclingEvent: save_recycling_event,
    PetFeeding: save_pet_feeding,
    BreakingEvent: save_breaking_event,
}
