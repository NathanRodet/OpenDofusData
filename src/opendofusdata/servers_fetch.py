"""One-off download of the game server list from the public DofusDB API (stdlib only)."""

import time
from dataclasses import dataclass
from pathlib import Path

from opendofusdata.game_servers import CLASSIC_GAME_TYPE_ID
from opendofusdata.names_build import build_type_names
from opendofusdata.names_fetch import (
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
from opendofusdata.servers_build import build_servers, write_servers_csv

GAME_TYPES_PATH = "/server-game-types"
SERVERS_PATH = "/servers"
GAME_TYPES_SELECT = "&$select[]=id&$select[]=name"
SERVERS_SELECT = ("&$select[]=id&$select[]=name&$select[]=gameTypeId"
                  "&$select[]=communityId")


@dataclass(frozen=True)
class ServersSummary(FetchSummary):
    """The download summary plus the counts around the classic-only filter."""

    received: int = 0
    excluded: int = 0


def download_game_servers(
    output: Path, fetch: FetchJson = http_get_json, *, classic_only: bool = True,
    page_size: int = PAGE_SIZE,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
    progress: Progress = print,
) -> ServersSummary:
    """Download the servers (count checked against the API total), keep the classic ones, write."""
    requester = Requester(fetch, sleep, request_delay)
    raw_types = collect_all(requester, GAME_TYPES_PATH, GAME_TYPES_SELECT, page_size, progress)
    raw_servers = collect_all(requester, SERVERS_PATH, SERVERS_SELECT, page_size, progress)
    result = build_servers(raw_servers, build_type_names(raw_types))
    kept = [server for server in result.servers
            if not classic_only or server.game_type_id == CLASSIC_GAME_TYPE_ID]
    write_servers_csv(kept, Path(output))
    return ServersSummary(len(kept), result.skipped, result.duplicates, Path(output),
                          Path(output).stat().st_size, len(raw_servers),
                          len(result.servers) - len(kept))
