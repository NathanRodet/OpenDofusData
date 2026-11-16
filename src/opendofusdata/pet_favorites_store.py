"""The favourite resources and crafts of the player, kept in config.json (one list per page)."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

PET_FAVORITES_KEY = "pet_favorites"
CRAFT_FAVORITES_KEY = "craft_favorites"


def load_favorites(config_path: Path, key: str = PET_FAVORITES_KEY) -> set[int]:
    """The favourite item ids saved under this key; anything that is not a whole number is ignored."""
    saved = load_config(config_path).get(key)
    return {item for item in saved if isinstance(item, int) and not isinstance(item, bool)} \
        if isinstance(saved, list) else set()


def toggle_favorite(config_path: Path, item_id: int, key: str = PET_FAVORITES_KEY) -> bool:
    """Add the item to the favourites, or remove it when it already is one; False when not saved."""
    favorites = load_favorites(config_path, key)
    favorites.symmetric_difference_update({item_id})
    try:
        save_config(config_path, {**load_config(config_path), key: sorted(favorites)})
    except OSError as error:
        logger.warning("favori non enregistré : %s", error)
        return False
    return True
