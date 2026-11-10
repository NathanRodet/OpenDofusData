"""CLI commands servers-update and servers, and the --server name normalisation."""

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.commands import format_table
from dofus_prices.game_servers import DEFAULT_SERVERS_PATH, GameServer, canonical_name, load_servers
from dofus_prices.names_build import NamesFetchError
from dofus_prices.names_commands import INTERRUPTED_MESSAGE
from dofus_prices.names_fetch import (
    REQUEST_DELAY_SECONDS,
    FetchJson,
    FetchSummary,
    Sleep,
    http_get_json,
)
from dofus_prices.servers_fetch import download_game_servers

UNKNOWN_SERVER = "unknown"
DEV_RUN = r".\dev.ps1 run"
UPDATE_NOTICE = (
    "Cette commande contacte api.dofusdb.fr une seule fois pour télécharger la liste des "
    "serveurs de jeu (quelques requêtes). La capture, elle, reste hors ligne."
)
LIST_NOTE = ("Liste issue de DofusDB : elle peut contenir des serveurs qui n'existent pas "
             "dans Dofus 3.")
NO_SERVERS_MESSAGE = ("Liste des serveurs absente ou vide : {path}. "
                      f"Télécharge-la d'abord avec : {DEV_RUN} servers-update")
UNLISTED_WARNING = ("serveur « {name} » absent de la liste "
                    "(servers-update pour la mettre à jour)")
SERVER_HEADERS = ("id", "nom", "type")


def add_servers_commands(commands: argparse._SubParsersAction) -> None:
    """Register servers-update and servers."""
    update = commands.add_parser("servers-update",
                                 help="télécharge la liste des serveurs de jeu (DofusDB)")
    update.add_argument("--output", default=DEFAULT_SERVERS_PATH,
                        help=f"fichier CSV à écrire (défaut : {DEFAULT_SERVERS_PATH})")
    listing = commands.add_parser("servers", help="affiche la liste des serveurs de jeu")
    listing.add_argument("--servers", default=DEFAULT_SERVERS_PATH,
                         help=f"fichier CSV des serveurs (défaut : {DEFAULT_SERVERS_PATH})")


def _print_summary(summary: FetchSummary) -> None:
    print(f"{summary.rows} serveurs écrits dans {summary.path} ({summary.size_bytes} octets), "
          f"{summary.skipped} ignoré(s) sans nom, {summary.duplicates} doublon(s).")


def servers_update_command(
    arguments: argparse.Namespace, fetch: FetchJson = http_get_json,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
) -> int:
    """Download the game server list (one of the two commands that use the network)."""
    print(UPDATE_NOTICE)
    try:
        summary = download_game_servers(Path(arguments.output), fetch,
                                        request_delay=request_delay, sleep=sleep)
    except NamesFetchError as error:
        return fail(str(error))
    except KeyboardInterrupt:
        return fail(INTERRUPTED_MESSAGE)
    _print_summary(summary)
    return EXIT_OK


def _sort_key(server: GameServer) -> tuple[str, str]:
    return server.game_type.casefold(), server.name.casefold()


def servers_command(arguments: argparse.Namespace) -> int:
    """Print the game servers as an aligned table, sorted by type then name."""
    servers = load_servers(arguments.servers)
    if not servers:
        print(NO_SERVERS_MESSAGE.format(path=arguments.servers))
        return EXIT_OK
    print(LIST_NOTE)
    rows = [(server.server_id, server.name, server.game_type)
            for server in sorted(servers, key=_sort_key)]
    print(format_table(SERVER_HEADERS, rows))
    return EXIT_OK


def resolve_server_name(name: str, path: str = DEFAULT_SERVERS_PATH) -> str:
    """Return the listed spelling of a --server name; warn once if the list lacks it."""
    servers = load_servers(path)
    if not servers or name == UNKNOWN_SERVER:
        return name
    canonical = canonical_name(servers, name)
    if canonical is None:
        print(UNLISTED_WARNING.format(name=name))
        return name
    return canonical


SERVER_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "servers-update": servers_update_command,
    "servers": servers_command,
}
