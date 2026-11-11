"""Turns raw DofusDB servers into sanitised list entries and writes the CSV: no network."""

from dataclasses import dataclass
from pathlib import Path

from opendofusdata.game_servers import SERVERS_CSV_HEADER, GameServer
from opendofusdata.names_build import (
    localized_name,
    require_id,
    write_csv_atomically,
)


@dataclass(frozen=True)
class ServersBuildResult:
    """Servers ready to write, plus what was left out."""

    servers: list[GameServer]
    skipped: int
    duplicates: int


def _optional_number(raw: dict, key: str) -> int | None:
    value = raw.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _build_server(raw: dict, name: str, type_names: dict[int, str]) -> GameServer:
    type_id = _optional_number(raw, "gameTypeId")
    return GameServer(require_id(raw), name, type_id, type_names.get(type_id, ""),
                      _optional_number(raw, "communityId"))


def build_servers(raw_servers: list[object], type_names: dict[int, str]) -> ServersBuildResult:
    """Build servers sorted by id: French name, else English, else skipped; first id wins."""
    servers: dict[int, GameServer] = {}
    skipped = duplicates = 0
    for raw in raw_servers:
        identifier = require_id(raw)
        name = localized_name(raw, "fr") or localized_name(raw, "en")
        if identifier in servers:
            duplicates += 1
        elif not name:
            skipped += 1
        else:
            servers[identifier] = _build_server(raw, name, type_names)
    return ServersBuildResult([servers[key] for key in sorted(servers)], skipped, duplicates)


def write_servers_csv(servers: list[GameServer], path: Path) -> None:
    """Write the servers CSV atomically (header, rows sorted as given)."""
    rows = [(server.server_id, server.name,
             "" if server.game_type_id is None else server.game_type_id, server.game_type,
             "" if server.community_id is None else server.community_id)
            for server in servers]
    write_csv_atomically(SERVERS_CSV_HEADER, rows, path)
