"""Download the item names and servers from DofusDB and load them into the player's database."""

import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from opendofusdata.app_config import default_config_path
from opendofusdata.game_servers import load_servers
from opendofusdata.item_labels import read_only_uri
from opendofusdata.item_names import ItemNames
from opendofusdata.names_db import count_items, replace_items
from opendofusdata.names_fetch import (
    REQUEST_DELAY_SECONDS, FetchJson, Sleep, download_item_names, http_get_json,
)
from opendofusdata.servers_fetch import download_game_servers
from opendofusdata.storage import PriceStore

logger = logging.getLogger(__name__)

ITEMS_FILE_NAME = "items.csv"
SERVERS_FILE_NAME = "servers.csv"


@dataclass(frozen=True)
class RefreshResult:
    """How many items and servers ended up in the database."""

    items: int
    servers: int


def default_data_directory() -> Path:
    """Where the downloaded reference files live: next to the user's config.json."""
    return default_config_path().parent


def _ignore_progress(message: str) -> None:
    logger.debug("%s", message)


def refresh_reference_data(
    database_path: str, data_directory: Path, fetch: FetchJson = http_get_json,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
) -> RefreshResult:
    """Download names and servers (a few hundred requests), then replace them in the database."""
    items_path = data_directory / ITEMS_FILE_NAME
    servers_path = data_directory / SERVERS_FILE_NAME
    data_directory.mkdir(parents=True, exist_ok=True)
    download_item_names(items_path, fetch, request_delay=request_delay, sleep=sleep,
                        progress=_ignore_progress)
    download_game_servers(servers_path, fetch, request_delay=request_delay, sleep=sleep,
                          progress=_ignore_progress)
    servers = load_servers(servers_path)
    store = PriceStore(database_path)
    try:
        items = replace_items(store.connection, ItemNames.load(items_path).entries(), servers or None)
    finally:
        store.close()
    return RefreshResult(items, len(servers))


def loaded_item_count(database_path: str) -> int:
    """Number of item names in the database; 0 when it is absent or unreadable (never creates it)."""
    if not Path(database_path).is_file():
        return 0
    try:
        with closing(sqlite3.connect(read_only_uri(database_path), uri=True)) as connection:
            return count_items(connection)
    except sqlite3.Error as error:
        logger.info("noms d'objets illisibles dans %s (%s)", database_path, error)
        return 0
