"""Experience typed by the players for a resource (x resources gave y XP), kept in SQLite and shared.

Every change is a snapshot of the totals of one resource: the latest snapshot of a player is what counts, and a
snapshot of 0 and 0 clears the resource. Mine are sent to the server; the other players' come back marked remote.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from opendofusdata.app_config import load_config, save_config
from opendofusdata.pet_economy import ResourceExperience
from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE
from opendofusdata.timeutil import format_utc

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_SECONDS = 30.0
PET_MANUAL_KEY = "pet_manual_experience"  # where older versions kept the totals (config.json)
UNITS_FIELD = "units"
EXPERIENCE_FIELD = "experience"
LATEST_SQL = """
    SELECT item_id, units, experience FROM (
        SELECT item_id, units, experience, ROW_NUMBER() OVER (
            PARTITION BY item_id, COALESCE(source_key_id, '') ORDER BY captured_at DESC, id DESC) AS rank
        FROM pet_manual_entries WHERE origin = ?) WHERE rank = 1"""


def _totals(connection: sqlite3.Connection, origin: str) -> dict[int, ResourceExperience]:
    """The latest snapshot of every player for the origin, added up per resource (cleared ones count for nothing)."""
    totals: dict[int, ResourceExperience] = {}
    for item_id, units, experience in connection.execute(LATEST_SQL, (origin,)):
        if units > 0 and experience > 0:
            known = totals.get(item_id, ResourceExperience(item_id, 0, 0, 0))
            totals[item_id] = ResourceExperience(item_id, 0, known.units + units, known.experience + experience)
    return totals


def own_manual(connection: sqlite3.Connection) -> dict[int, ResourceExperience]:
    """What this player typed, per resource."""
    return _totals(connection, ORIGIN_LOCAL)


def load_manual(connection: sqlite3.Connection) -> dict[int, ResourceExperience]:
    """What every player typed (mine and the others'), added up per resource."""
    merged = own_manual(connection)
    for item_id, other in _totals(connection, ORIGIN_REMOTE).items():
        known = merged.get(item_id, ResourceExperience(item_id, 0, 0, 0))
        merged[item_id] = ResourceExperience(item_id, 0, known.units + other.units, known.experience + other.experience)
    return merged


def _snapshot(connection: sqlite3.Connection, item_id: int, units: int, experience: int, moment: datetime | None) -> None:
    stamp = format_utc(moment or datetime.now(timezone.utc))
    with connection:
        connection.execute("INSERT INTO pet_manual_entries (captured_at, item_id, units, experience, origin) "
                           "VALUES (?, ?, ?, ?, ?)", (stamp, item_id, units, experience, ORIGIN_LOCAL))


def add_manual(connection: sqlite3.Connection, item_id: int, units: int, experience: int,
               moment: datetime | None = None) -> bool:
    """Add `units` resources that gave `experience` XP to my totals for the resource; False when not saved."""
    known = own_manual(connection).get(item_id, ResourceExperience(item_id, 0, 0, 0))
    try:
        _snapshot(connection, item_id, known.units + units, known.experience + experience, moment)
    except sqlite3.Error as error:
        logger.warning("expérience saisie non enregistrée : %s", error)
        return False
    return True


def remove_manual(connection: sqlite3.Connection, item_id: int, moment: datetime | None = None) -> bool:
    """Forget everything I typed for the resource (a snapshot of 0 and 0, so the others forget it too)."""
    try:
        _snapshot(connection, item_id, 0, 0, moment)
    except sqlite3.Error as error:
        logger.warning("expérience saisie non retirée : %s", error)
        return False
    return True


def _config_entries(config_path: Path) -> dict[int, tuple[int, int]]:
    saved = load_config(config_path).get(PET_MANUAL_KEY)
    entries = {}
    for name, entry in (saved.items() if isinstance(saved, dict) else ()):
        units, experience = (entry.get(UNITS_FIELD), entry.get(EXPERIENCE_FIELD)) if isinstance(entry, dict) else (0, 0)
        if name.isdigit() and isinstance(units, int) and isinstance(experience, int) and units > 0 and experience > 0:
            entries[int(name)] = (units, experience)
    return entries


def import_config_manual(connection: sqlite3.Connection, config_path: Path) -> int:
    """Move the totals older versions kept in config.json into the database (once); returns how many."""
    entries = _config_entries(config_path)
    config = load_config(config_path)
    if PET_MANUAL_KEY not in config:
        return 0
    known = own_manual(connection)
    for item_id, (units, experience) in entries.items():
        if item_id not in known:
            _snapshot(connection, item_id, units, experience, None)
    save_config(config_path, {name: value for name, value in config.items() if name != PET_MANUAL_KEY})
    return len(entries)


def move_config_entries(database_path: str, config_path: Path) -> int:
    """Open the database and move the totals older versions kept in config.json into it; 0 when nothing moved."""
    if PET_MANUAL_KEY not in load_config(config_path):
        return 0
    try:
        with closing(sqlite3.connect(database_path, timeout=BUSY_TIMEOUT_SECONDS)) as connection:
            return import_config_manual(connection, config_path)
    except (sqlite3.Error, OSError) as error:
        logger.warning("saisies de familiers non déplacées vers la base : %s", error)
        return 0
