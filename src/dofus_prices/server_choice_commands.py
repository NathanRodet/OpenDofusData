"""Console wiring of the remembered server: run-time resolution and the server command."""

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from dofus_prices.app_config import default_config_path, load_config, save_config
from dofus_prices.capture_errors import EXIT_OK, fail
from dofus_prices.game_servers import DEFAULT_SERVERS_PATH, available_servers, canonical_name
from dofus_prices.server_choice import SERVER_KEY, ServerResolution, resolve_server

logger = logging.getLogger(__name__)

SOURCE_LABELS = {"option": " (option)", "config": " (mémorisé ; --choose-server pour changer)", "prompt": " (choisi)",
                 "default": ""}
NO_SERVER_MESSAGE = "Aucun serveur mémorisé."
SHOW_MESSAGE = "Serveur mémorisé : {name}"
SET_MESSAGE = "Serveur mémorisé : {name} (enregistré dans {path})"
EMPTY_NAME_MESSAGE = "Nom de serveur vide."
UNLISTED_NAME_MESSAGE = ("Serveur « {name} » absent de la liste. Mets la liste à jour avec "
                         r".\dev.ps1 run servers-update, puis choisis un nom de .\dev.ps1 run servers.")
INTERRUPTED_MESSAGE = "Interrompu, aucune capture lancée."
EXIT_INTERRUPTED = 130
CLEARED_MESSAGE = "Serveur oublié."
SAVE_FAILED = "Impossible d'écrire la configuration {path} : {error}"
SAVE_WARNING = "Choix non mémorisé : écriture de {path} impossible ({error})"


def is_interactive() -> bool:
    """True when both stdin and stdout are terminals."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def add_server_command(commands: argparse._SubParsersAction) -> None:
    """Register the server command (show, --set, --clear)."""
    parser = commands.add_parser("server", help="affiche, définit ou oublie le serveur mémorisé")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--set", dest="set_name", default=None, metavar="NOM",
                       help="mémorise ce serveur")
    group.add_argument("--clear", action="store_true", help="oublie le serveur mémorisé")


def _resolve_with_prompt(arguments: argparse.Namespace, config: dict[str, object]) -> ServerResolution:
    try:
        return resolve_server(
            arguments.server, available_servers(DEFAULT_SERVERS_PATH), config,
            is_interactive(), arguments.choose_server, input, print)
    except KeyboardInterrupt:
        print(INTERRUPTED_MESSAGE)
        raise SystemExit(EXIT_INTERRUPTED) from None


def resolve_run_server(arguments: argparse.Namespace) -> None:
    """Fill arguments.server and arguments.server_label for a capture session."""
    path = default_config_path()
    config = load_config(path)
    resolution = _resolve_with_prompt(arguments, config)
    if resolution.save:
        try:
            save_config(path, {**config, SERVER_KEY: resolution.name})
        except OSError as error:
            logger.warning(SAVE_WARNING.format(path=path, error=error))
    arguments.server = resolution.name
    arguments.server_label = SOURCE_LABELS[resolution.source]


def _show(config: dict[str, object]) -> int:
    saved = config.get(SERVER_KEY)
    print(SHOW_MESSAGE.format(name=saved) if isinstance(saved, str) and saved else NO_SERVER_MESSAGE)
    return EXIT_OK


def _write(path: Path, config: dict[str, object]) -> int:
    try:
        save_config(path, config)
    except OSError as error:
        return fail(SAVE_FAILED.format(path=path, error=error))
    return EXIT_OK


def _set(path: Path, config: dict[str, object], name: str) -> int:
    if not name.strip():
        return fail(EMPTY_NAME_MESSAGE)
    canonical = canonical_name(available_servers(DEFAULT_SERVERS_PATH), name.strip())
    if canonical is None:
        return fail(UNLISTED_NAME_MESSAGE.format(name=name.strip()))
    code = _write(path, {**config, SERVER_KEY: canonical})
    if code == EXIT_OK:
        print(SET_MESSAGE.format(name=canonical, path=path))
    return code


def _clear(path: Path, config: dict[str, object]) -> int:
    if SERVER_KEY not in config:
        print(NO_SERVER_MESSAGE)
        return EXIT_OK
    remaining = {key: value for key, value in config.items() if key != SERVER_KEY}
    code = _write(path, remaining)
    if code == EXIT_OK:
        print(CLEARED_MESSAGE)
    return code


def server_command(arguments: argparse.Namespace) -> int:
    """Show, set (--set) or clear (--clear) the remembered server without capturing."""
    path = default_config_path()
    config = load_config(path)
    if arguments.set_name is not None:
        return _set(path, config, arguments.set_name)
    if arguments.clear:
        return _clear(path, config)
    return _show(config)


CHOICE_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"server": server_command}
