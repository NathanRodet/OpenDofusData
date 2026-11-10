"""Game server list (id -> name, type) loaded from the local CSV: pure, no network."""

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SERVERS_PATH = "data/servers.csv"
SERVERS_CSV_HEADER = ("id", "name_fr", "game_type_id", "game_type_fr", "community_id")


@dataclass(frozen=True)
class GameServer:
    """One game server of the list."""

    server_id: int
    name: str
    game_type_id: int | None
    game_type: str
    community_id: int | None


def _optional_int(text: str) -> int | None:
    return int(text) if text else None


def _parse_row(row: list[str]) -> GameServer:
    server_id, name, game_type_id, game_type, community_id = row
    if not name.strip():
        raise ValueError("nom vide")
    return GameServer(int(server_id), name, _optional_int(game_type_id), game_type,
                      _optional_int(community_id))


def _read_servers(path: Path) -> list[GameServer]:
    servers: list[GameServer] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            try:
                servers.append(_parse_row(row))
            except ValueError as error:
                logger.warning("ligne %d de la liste des serveurs ignorée (%s)",
                               reader.line_num, error)
    return servers


def load_servers(path: str | Path) -> list[GameServer]:
    """Load the CSV file; a missing or unreadable file gives an empty list."""
    file_path = Path(path)
    if not file_path.is_file():
        return []
    try:
        return _read_servers(file_path)
    except (OSError, UnicodeError, csv.Error) as error:
        logger.warning("liste des serveurs illisible (%s : %s)", file_path, error)
        return []


def canonical_name(servers: Sequence[GameServer], text: str) -> str | None:
    """Return the listed spelling of a server name (exact, case-insensitive), else None."""
    wanted = text.casefold()
    for server in servers:
        if server.name.casefold() == wanted:
            return server.name
    return None
