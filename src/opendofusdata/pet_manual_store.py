"""Experience values typed by the player for a resource (x resources gave y XP), kept in config.json."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config
from opendofusdata.pet_economy import ResourceExperience

logger = logging.getLogger(__name__)

PET_MANUAL_KEY = "pet_manual_experience"
UNITS_FIELD = "units"
EXPERIENCE_FIELD = "experience"


def _saved(config_path: Path) -> dict[str, dict[str, int]]:
    saved = load_config(config_path).get(PET_MANUAL_KEY)
    return {name: entry for name, entry in saved.items() if isinstance(entry, dict)} if isinstance(saved, dict) else {}


def load_manual(config_path: Path) -> dict[int, ResourceExperience]:
    """The typed experience per resource (all entries added up); malformed entries are ignored."""
    result = {}
    for name, entry in _saved(config_path).items():
        units, experience = entry.get(UNITS_FIELD), entry.get(EXPERIENCE_FIELD)
        if name.isdigit() and isinstance(units, int) and isinstance(experience, int) and units > 0 and experience > 0:
            result[int(name)] = ResourceExperience(int(name), 0, units, experience)
    return result


def _write(config_path: Path, saved: dict[str, dict[str, int]]) -> bool:
    try:
        save_config(config_path, {**load_config(config_path), PET_MANUAL_KEY: saved})
    except OSError as error:
        logger.warning("expérience saisie non enregistrée : %s", error)
        return False
    return True


def add_manual(config_path: Path, item_id: int, units: int, experience: int) -> bool:
    """Add `units` resources that gave `experience` XP to the resource's typed totals; False when not saved."""
    saved = _saved(config_path)
    known = saved.get(str(item_id), {})
    saved[str(item_id)] = {UNITS_FIELD: known.get(UNITS_FIELD, 0) + units,
                           EXPERIENCE_FIELD: known.get(EXPERIENCE_FIELD, 0) + experience}
    return _write(config_path, saved)


def remove_manual(config_path: Path, item_id: int) -> bool:
    """Forget everything typed for the resource; False when not saved."""
    saved = _saved(config_path)
    saved.pop(str(item_id), None)
    return _write(config_path, saved)
