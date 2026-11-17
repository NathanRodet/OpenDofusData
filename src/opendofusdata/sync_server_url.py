"""The synchronisation server address: set in Réglages, else from the .env, else the built-in default."""

import logging
from pathlib import Path

from opendofusdata.app_config import load_config, save_config
from opendofusdata.env_file import canonical_origin
from opendofusdata.sync_client import resolve_server_url

logger = logging.getLogger(__name__)
SERVER_URL_CONFIG = "sync_server_url"
SCHEME_SEPARATOR = "://"
HTTPS_PREFIX = "https://"


def origin_from_text(text: str) -> str | None:
    """The https address for what the player typed: a bare domain (https is added) or a full https address."""
    typed = text.strip()
    if not typed or typed.endswith(SCHEME_SEPARATOR):
        return None
    typed = typed.removesuffix("/")
    origin = canonical_origin(typed if SCHEME_SEPARATOR in typed else HTTPS_PREFIX + typed)
    return origin if origin is not None and "." in display_address(origin).split(":")[0] else None


def display_address(origin: str | None) -> str:
    """The address as the player types it: the domain alone, without https."""
    return (origin or "").removeprefix(HTTPS_PREFIX)


def configured_server_url(config_path: Path, env_path: Path) -> str | None:
    """The address to use: the one saved in the settings, else the .env, else the default; None when none exists."""
    saved = load_config(config_path).get(SERVER_URL_CONFIG)
    valid = canonical_origin(saved) if isinstance(saved, str) else None
    return valid or resolve_server_url(env_path)


def save_server_url(config_path: Path, text: str) -> bool:
    """Save the address typed by the player (an empty text removes it); False when refused or not written."""
    address = text.strip()
    origin = origin_from_text(address)
    if address and origin is None:
        return False
    config = dict(load_config(config_path))
    if origin is None:
        config.pop(SERVER_URL_CONFIG, None)
    else:
        config[SERVER_URL_CONFIG] = origin
    try:
        save_config(config_path, config)
    except OSError as error:
        logger.warning("adresse du serveur non enregistrée : %s", error)
        return False
    return True
