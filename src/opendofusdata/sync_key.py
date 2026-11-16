"""The synchronisation key of the player: format check, cleaning and storage in config.json."""

import logging
import re
from pathlib import Path

from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

# The same format as the server (src/server/keyserver/signed_keys.py), checked by the same test key.
KEY_PATTERN = re.compile(r"^odk1\.[A-Za-z0-9_-]{11}\.[A-Za-z0-9_-]{43}$")
SYNC_KEY_CONFIG = "sync_api_key"


def clean_key(text: str) -> str:
    """The pasted text without any space, tab or line break."""
    return "".join(text.split())


def key_format_ok(key: str) -> bool:
    """True when the text has exactly the shape of a key (the server alone can tell if it is valid)."""
    return KEY_PATTERN.fullmatch(key) is not None


def load_sync_key(config_path: Path) -> str | None:
    """The saved key, or None when absent or not well formed."""
    saved = load_config(config_path).get(SYNC_KEY_CONFIG)
    return saved if isinstance(saved, str) and key_format_ok(saved) else None


def save_sync_key(config_path: Path, key: str | None) -> bool:
    """Save the key (None removes it) and keep the other settings; False when refused or not written."""
    if key is not None and not key_format_ok(key):
        return False
    config = dict(load_config(config_path))
    if key is None:
        config.pop(SYNC_KEY_CONFIG, None)
    else:
        config[SYNC_KEY_CONFIG] = key
    try:
        save_config(config_path, config)
    except OSError as error:
        logger.warning("clé de synchronisation non enregistrée : %s", error)
        return False
    return True
