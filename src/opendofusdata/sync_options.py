"""The options of a synchronisation round: entering a key is the player's consent, nothing else to tick."""

from pathlib import Path

from opendofusdata.sync_client import resolve_server_url
from opendofusdata.sync_engine import SyncOptions
from opendofusdata.sync_key import load_sync_key


def load_sync_options(config_path: Path, env_path: Path) -> SyncOptions | None:
    """The options of the next round, read fresh: both directions on once a key and a server address exist.

    Removing the key (or having no server address) stops the synchronisation; None means nothing to do.
    """
    key, base_url = load_sync_key(config_path), resolve_server_url(env_path)
    if not key or not base_url:
        return None
    return SyncOptions(base_url, key, True, True)
