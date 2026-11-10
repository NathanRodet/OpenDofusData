"""Console wiring of the server addresses: server --learn/--ips/--forget and the run resolver."""

import argparse
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from dofus_prices.app_config import default_config_path, load_config, save_config
from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.commands import format_table
from dofus_prices.game_servers import DEFAULT_SERVERS_PATH, UNKNOWN_SERVER, load_servers
from dofus_prices.netstat_parse import parse_netstat
from dofus_prices.server_choice import SERVER_KEY, normalise_server_name
from dofus_prices.server_detect import LEARNED_MESSAGE, ServerResolver
from dofus_prices.server_ips import IPS_KEY, ServerIps, normalise_server_ip

logger = logging.getLogger(__name__)

NETSTAT_COMMAND = ["netstat", "-n", "-p", "tcp"]
NETSTAT_TIMEOUT_SECONDS = 15
NETSTAT_ENCODING = "oem" if sys.platform == "win32" else "utf-8"
IPS_HEADERS = ("adresse", "serveur", "origine")
NO_NAME_MESSAGE = "Aucun serveur mémorisé : indique un nom avec « server --learn NOM »."
BAD_NAME_MESSAGE = "Nom de serveur invalide : indique le nom du serveur de jeu (pas « unknown »)."
NETSTAT_FAILED = "Impossible de lister les connexions avec netstat ({error})."
NO_CONNECTION_MESSAGE = "aucune connexion de jeu active : lance le jeu et connecte-toi"
SAVE_FAILED = "Impossible d'écrire la configuration {path} : {error}"
BAD_ADDRESS_MESSAGE = "Adresse invalide : une adresse IPv4 publique est attendue."
FORGOTTEN_MESSAGE = "Adresse oubliée."
NOT_LEARNED_MESSAGE = "Cette adresse n'a pas été apprise (les adresses livrées ne s'oublient pas)."
RUN_EXPLICIT_NOTE = " L'adresse du serveur de jeu sera apprise pour ce serveur."
RUN_REMEMBERED_NOTE = " Serveur reconnu par adresse ; adresse inconnue : « unknown »."


def run_netstat() -> str:
    """Run `netstat -n -p tcp` (fixed arguments, no shell) and return its text."""
    completed = subprocess.run(NETSTAT_COMMAND, capture_output=True, timeout=NETSTAT_TIMEOUT_SECONDS,
                               check=True)
    return completed.stdout.decode(NETSTAT_ENCODING, errors="replace")


def _write_ips(path: Path, config: dict[str, object], ips: ServerIps) -> int:
    try:
        save_config(path, {**config, IPS_KEY: ips.to_config()})
    except OSError as error:
        return fail(SAVE_FAILED.format(path=path, error=error))
    return EXIT_OK


class _CommandError(Exception):
    """A user-facing failure of a server address command (the message is French)."""


def _learn_name(requested: str, config: dict[str, object]) -> str:
    name = requested.strip() or str(config.get(SERVER_KEY) or "").strip()
    if not name:
        raise _CommandError(NO_NAME_MESSAGE)
    if name == UNKNOWN_SERVER:
        raise _CommandError(BAD_NAME_MESSAGE)
    return normalise_server_name(name, load_servers(DEFAULT_SERVERS_PATH), print)


def _active_addresses(netstat: Callable[[], str]) -> list[str]:
    try:
        addresses = parse_netstat(netstat())
    except (OSError, subprocess.SubprocessError) as error:
        raise _CommandError(NETSTAT_FAILED.format(error=error)) from error
    if not addresses:
        raise _CommandError(NO_CONNECTION_MESSAGE)
    return addresses


def learn_command(arguments: argparse.Namespace, netstat: Callable[[], str] = run_netstat) -> int:
    """Associate the game server addresses of the active connections with a server name."""
    path = default_config_path()
    config = load_config(path)
    try:
        name = _learn_name(arguments.learn_name, config)
        addresses = _active_addresses(netstat)
    except _CommandError as error:
        return fail(str(error))
    ips = ServerIps(config.get(IPS_KEY))
    for address in addresses:
        ips.learn(address, name)
    code = _write_ips(path, config, ips)
    if code == EXIT_OK:
        for address in addresses:
            print(LEARNED_MESSAGE.format(ip=address, server=name))
    return code


def ips_command(arguments: argparse.Namespace) -> int:
    """List the known game server addresses (bundled and learned)."""
    ips = ServerIps(load_config(default_config_path()).get(IPS_KEY))
    print(format_table(IPS_HEADERS, ips.entries()))
    return EXIT_OK


def forget_command(arguments: argparse.Namespace) -> int:
    """Remove a learned address from the configuration."""
    path = default_config_path()
    config = load_config(path)
    ips = ServerIps(config.get(IPS_KEY))
    if normalise_server_ip(arguments.forget_ip) is None:
        return fail(BAD_ADDRESS_MESSAGE)
    if not ips.forget(arguments.forget_ip):
        return fail(NOT_LEARNED_MESSAGE)
    code = _write_ips(path, config, ips)
    if code == EXIT_OK:
        print(FORGOTTEN_MESSAGE)
    return code


def build_server_resolver(arguments: argparse.Namespace) -> ServerResolver:
    """Build the per-flow server resolver of a capture session and describe it for the start line."""
    path = default_config_path()
    explicit = arguments.server_explicit

    def persist(learned: dict[str, str]) -> None:
        save_config(path, {**load_config(path), IPS_KEY: learned})

    arguments.server_note = RUN_EXPLICIT_NOTE if explicit else RUN_REMEMBERED_NOTE
    return ServerResolver(ServerIps(load_config(path).get(IPS_KEY)), arguments.server, explicit,
                          persist, print)
