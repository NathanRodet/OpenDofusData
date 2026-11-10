"""Command-line entry point: parser construction and dispatch."""

import argparse
import logging
import sys
from collections.abc import Callable

from dofus_prices.capture import CaptureAborted, PacketPipeline, direction_of, run_capture
from dofus_prices.capture_errors import (
    EXIT_OK,
    EXIT_USAGE,
    CaptureFunction,
    fail,
    run_guarded_capture,
)
from dofus_prices.commands import (
    export_csv_command,
    history_command,
    prices_command,
    stats_command,
)
from dofus_prices.discovery import DiscoveryLogger, LogSizeLimitReached
from dofus_prices.framing import Envelope
from dofus_prices.names_commands import add_names_commands, names_update_command
from dofus_prices.run_pipeline import Clock, run_command, utc_now
from dofus_prices.storage import LOT_SIZES, MARKET_PERIODS
from dofus_prices.tcp import FlowKey

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "captures/discovery.jsonl"
DEFAULT_DATABASE = "prices.db"
DEFAULT_SERVER = "unknown"

INCLUDE_TEXT_WARNING = (
    "Attention : le journal peut contenir des données personnelles (chat, identifiants). "
    "Relisez-le avant de le partager."
)
HEX_TYPES_NOTICE = (
    "Aperçus d'octets (hex) activés uniquement pour les types de message : {names}. "
    "Les autres types restent sans aperçu. Ces aperçus peuvent contenir des données "
    "personnelles si ces types transportent du chat ou des identifiants : relisez le "
    "journal avant de le partager."
)


def parse_hex_types(raw: str) -> frozenset[str]:
    """Parse comma-separated message type names (letters and digits only)."""
    names = raw.split(",")
    if not all(name.isascii() and name.isalnum() for name in names):
        raise argparse.ArgumentTypeError(
            "noms de types invalides (lettres et chiffres, séparés par des virgules)"
        )
    return frozenset(names)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="dofus_prices")
    commands = parser.add_subparsers(dest="command")
    discover = commands.add_parser("discover", help="journalise la structure des messages")
    discover.add_argument("--interface", default=None, help="interface réseau à écouter")
    discover.add_argument("--output", default=DEFAULT_OUTPUT, help="fichier de log JSON Lines")
    discover.add_argument("--include-text", action="store_true",
                          help="inclut des aperçus texte/hex (données personnelles possibles)")
    discover.add_argument("--hex-types", type=parse_hex_types, default=frozenset(),
                          metavar="NAMES",
                          help="types de message (ex. jzs,ire) avec aperçu hex de leurs octets (données personnelles possibles)")
    _add_database_commands(commands)
    add_names_commands(commands)
    return parser


def _database_option(command: argparse.ArgumentParser) -> None:
    command.add_argument("--db", default=DEFAULT_DATABASE, help="base SQLite (défaut : prices.db)")


def _add_run_command(commands: argparse._SubParsersAction) -> None:
    run_parser = commands.add_parser("run", help="capture et enregistre les prix de l'HDV")
    _database_option(run_parser)
    run_parser.add_argument("--interface", default=None, help="interface réseau à écouter")
    run_parser.add_argument("--server", default=DEFAULT_SERVER, help="nom du serveur de jeu enregistré")
    run_parser.add_argument("--verbose", action="store_true",
                            help="affiche en direct les valeurs décodées (tables) pendant la capture")


def _add_read_commands(commands: argparse._SubParsersAction) -> None:
    prices = commands.add_parser("prices", help="derniers prix par objet, serveur et lot")
    _database_option(prices)
    prices.add_argument("--item", type=int, default=None,
                        help="identifiant de l'objet (le trafic ne contient pas les noms)")
    history = commands.add_parser("history", help="historique des prix d'un objet")
    _database_option(history)
    history.add_argument("item_id", type=int, help="identifiant de l'objet (pas de nom)")
    history.add_argument("--lot", type=int, required=True, choices=LOT_SIZES, help="taille du lot")


def _add_stats_and_export(commands: argparse._SubParsersAction) -> None:
    stats = commands.add_parser("stats", help="dernières statistiques de marché d'un objet")
    _database_option(stats)
    stats.add_argument("item_id", type=int, help="identifiant de l'objet (pas de nom)")
    stats.add_argument("--period", choices=MARKET_PERIODS, default=None, help="période affichée")
    export = commands.add_parser("export-csv", help="exporte tous les prix en CSV")
    _database_option(export)
    export.add_argument("--output", required=True, help="fichier CSV à écrire")


def _add_database_commands(commands: argparse._SubParsersAction) -> None:
    _add_run_command(commands)
    _add_read_commands(commands)
    _add_stats_and_export(commands)


def _envelope_callback(
    discovery_logger: DiscoveryLogger,
) -> Callable[[Envelope, FlowKey], None]:
    def write(envelope: Envelope, key: FlowKey) -> None:
        try:
            discovery_logger.log(envelope, direction_of(key))
        except LogSizeLimitReached as error:
            raise CaptureAborted("limite de taille du journal atteinte") from error
        except OSError as error:
            raise CaptureAborted(str(error)) from error

    return write


def _capture_into(
    discovery_logger: DiscoveryLogger, interface: str | None, capture: CaptureFunction
) -> int:
    pipeline = PacketPipeline(_envelope_callback(discovery_logger))
    return run_guarded_capture(
        capture, pipeline, interface,
        lambda: f"Arrêt. {discovery_logger.logged_count} messages journalisés.",
        lambda error: (f"Écriture du journal impossible ({error}) après "
                       f"{discovery_logger.logged_count} messages."),
    )


def _discover(arguments: argparse.Namespace, capture: CaptureFunction) -> int:
    output = arguments.output
    try:
        discovery_logger = DiscoveryLogger(
            output, include_text=arguments.include_text, hex_types=arguments.hex_types
        )
    except OSError as error:
        return fail(f"Impossible d'écrire le journal {output} : {error}")
    print(f"Journal écrit dans {output}. Ctrl+C pour arrêter.")
    if arguments.include_text:
        print(INCLUDE_TEXT_WARNING)
    if arguments.hex_types:
        print(HEX_TYPES_NOTICE.format(names=", ".join(sorted(arguments.hex_types))))
    try:
        return _capture_into(discovery_logger, arguments.interface, capture)
    finally:
        discovery_logger.close()


READ_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "prices": prices_command,
    "history": history_command,
    "stats": stats_command,
    "export-csv": export_csv_command,
    "names-update": names_update_command,
}


def run(argv: list[str] | None, capture: CaptureFunction, now: Clock = utc_now) -> int:
    """Run the CLI with an injectable capture function and clock."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "discover":
        return _discover(arguments, capture)
    if arguments.command == "run":
        return run_command(arguments, capture, now)
    if arguments.command in READ_COMMANDS:
        return READ_COMMANDS[arguments.command](arguments)
    parser.print_help()
    return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    """Entry point returning the process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    return run(argv, run_capture)
