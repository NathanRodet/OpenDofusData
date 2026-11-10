"""One-off download of the game server list from the public DofusDB API (stdlib only)."""

import time
from pathlib import Path

from dofus_prices.names_build import build_type_names
from dofus_prices.names_fetch import (
    PAGE_SIZE,
    REQUEST_DELAY_SECONDS,
    FetchJson,
    FetchSummary,
    Progress,
    Requester,
    Sleep,
    collect_all,
    http_get_json,
)
from dofus_prices.servers_build import build_servers, write_servers_csv

GAME_TYPES_PATH = "/server-game-types"
SERVERS_PATH = "/servers"
GAME_TYPES_SELECT = "&$select[]=id&$select[]=name"
SERVERS_SELECT = ("&$select[]=id&$select[]=name&$select[]=gameTypeId"
                  "&$select[]=communityId")


def download_game_servers(
    output: Path, fetch: FetchJson = http_get_json, *, page_size: int = PAGE_SIZE,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
    progress: Progress = print,
) -> FetchSummary:
    """Download the game types then the servers and write the CSV list atomically."""
    requester = Requester(fetch, sleep, request_delay)
    raw_types = collect_all(requester, GAME_TYPES_PATH, GAME_TYPES_SELECT, page_size, progress)
    raw_servers = collect_all(requester, SERVERS_PATH, SERVERS_SELECT, page_size, progress)
    result = build_servers(raw_servers, build_type_names(raw_types))
    write_servers_csv(result.servers, Path(output))
    return FetchSummary(len(result.servers), result.skipped, result.duplicates,
                        Path(output), Path(output).stat().st_size)
