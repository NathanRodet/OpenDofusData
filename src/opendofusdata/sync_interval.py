"""How often the synchronisation polls the server (the stream wakes it sooner): the player's setting in config.json."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 10
MAX_INTERVAL_SECONDS = 300
DEFAULT_INTERVAL_SECONDS = 30
INTERVAL_STEP_SECONDS = 5
INTERVAL_CONFIG = "sync_interval_seconds"


def clamp_interval(value: object) -> int:
    """The interval kept inside the allowed range; the default for anything that is not a whole number."""
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


def load_sync_interval(config_path: Path) -> int:
    """The saved interval in seconds (default 30), always inside 10..300."""
    return clamp_interval(load_config(config_path).get(INTERVAL_CONFIG))


def save_sync_interval(config_path: Path, seconds: int) -> bool:
    """Save the interval (clamped); False when it could not be written."""
    try:
        save_config(config_path, {**load_config(config_path), INTERVAL_CONFIG: clamp_interval(seconds)})
    except OSError as error:
        logger.warning("intervalle de synchronisation non enregistré : %s", error)
        return False
    return True
