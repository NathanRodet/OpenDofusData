"""The send and receive settings of the player (both off by default) and the options of a synchronisation round."""

from collections.abc import Mapping
from pathlib import Path

from opendofusdata.app_config import load_config
from opendofusdata.sync_client import resolve_server_url
from opendofusdata.sync_engine import SyncOptions
from opendofusdata.sync_key import load_sync_key

SYNC_SEND_KEY = "sync_send"
SYNC_RECEIVE_KEY = "sync_receive"


def _enabled(config: Mapping[str, object], name: str) -> bool:
    """True only for a real boolean `true`; anything else (missing, text, number) counts as off."""
    return config.get(name) is True


def sync_send_enabled(config: Mapping[str, object]) -> bool:
    """Whether the player allows sending their prices."""
    return _enabled(config, SYNC_SEND_KEY)


def sync_receive_enabled(config: Mapping[str, object]) -> bool:
    """Whether the player allows receiving the prices of the other players."""
    return _enabled(config, SYNC_RECEIVE_KEY)


def config_with_sync_send(config: Mapping[str, object], enabled: bool) -> dict[str, object]:
    """Copy of the config with the send setting changed."""
    return {**config, SYNC_SEND_KEY: enabled}


def config_with_sync_receive(config: Mapping[str, object], enabled: bool) -> dict[str, object]:
    """Copy of the config with the receive setting changed."""
    return {**config, SYNC_RECEIVE_KEY: enabled}


def load_sync_options(config_path: Path, env_path: Path) -> SyncOptions | None:
    """The options of the next round, read fresh; None without a key, an address, or any direction switched on."""
    config = load_config(config_path)
    key, base_url = load_sync_key(config_path), resolve_server_url(env_path)
    send, receive = sync_send_enabled(config), sync_receive_enabled(config)
    if not key or not base_url or not (send or receive):
        return None
    return SyncOptions(base_url, key, send, receive)
