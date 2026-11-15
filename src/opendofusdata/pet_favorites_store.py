"""The favourite resources of the player, kept in config.json."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

PET_FAVORITES_KEY = "pet_favorites"


def load_favorites(config_path: Path) -> set[int]:
    """The favourite resource ids; anything that is not a whole number is ignored."""
    saved = load_config(config_path).get(PET_FAVORITES_KEY)
    return {item for item in saved if isinstance(item, int) and not isinstance(item, bool)} \
        if isinstance(saved, list) else set()


def toggle_favorite(config_path: Path, item_id: int) -> bool:
    """Add the resource to the favourites, or remove it when it already is one; False when not saved."""
    favorites = load_favorites(config_path)
    favorites.symmetric_difference_update({item_id})
    try:
        save_config(config_path, {**load_config(config_path), PET_FAVORITES_KEY: sorted(favorites)})
    except OSError as error:
        logger.warning("favori non enregistré : %s", error)
        return False
    return True
