"""SQL of the pet feedings table (schema, save and read helpers)."""

import json
import sqlite3
from dataclasses import asdict

from opendofusdata.records import PetFeeding, PetState

PETS_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS pet_feedings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT NOT NULL, captured_at TEXT NOT NULL,
        pet_item_id INTEGER NOT NULL, resources_json TEXT NOT NULL, before_json TEXT NOT NULL,
        after_json TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_pet_feedings_time ON pet_feedings (captured_at, id)",
)
INSERT_PET_SQL = ("INSERT INTO pet_feedings (server, captured_at, pet_item_id, resources_json, before_json, "
                  "after_json) VALUES (?, ?, ?, ?, ?, ?)")
SELECT_PET_SQL = ("SELECT server, captured_at, pet_item_id, resources_json, before_json, after_json "
                  "FROM pet_feedings ORDER BY captured_at, id")


def save_pet_feeding(connection: sqlite3.Connection, feeding: PetFeeding) -> None:
    """Append one pet upgrade (states stored as JSON objects, resources as [item id, quantity] pairs)."""
    connection.execute(INSERT_PET_SQL, (
        feeding.server, feeding.captured_at, feeding.pet_item_id, json.dumps(feeding.resources),
        json.dumps(asdict(feeding.before)), json.dumps(asdict(feeding.after))))


def pet_feedings(connection: sqlite3.Connection) -> list[PetFeeding]:
    """Every stored pet upgrade, oldest first."""
    feedings = []
    for server, captured_at, pet_item_id, resources_json, before_json, after_json in connection.execute(SELECT_PET_SQL):
        resources = tuple((item_id, quantity) for item_id, quantity in json.loads(resources_json))
        feedings.append(PetFeeding(server, pet_item_id, resources, PetState(**json.loads(before_json)),
                                   PetState(**json.loads(after_json)), captured_at))
    return feedings
