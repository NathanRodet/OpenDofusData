"""Command-line entry point: the discovery mode."""

import argparse
import logging
import sys
from collections.abc import Callable

from dofus_prices.capture import CaptureAborted, PacketPipeline, direction_of, run_capture
from dofus_prices.discovery import DiscoveryLogger
from dofus_prices.framing import Envelope
from dofus_prices.tcp import FlowKey

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "captures/discovery.jsonl"
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

CaptureFunction = Callable[[PacketPipeline, str | None], None]


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="dofus_prices")
    commands = parser.add_subparsers(dest="command")
    discover = commands.add_parser("discover", help="journalise la structure des messages")
    discover.add_argument("--interface", default=None, help="interface réseau à écouter")
    discover.add_argument("--output", default=DEFAULT_OUTPUT, help="fichier de log JSON Lines")
    return parser


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return EXIT_FAILED


def _envelope_callback(
    discovery_logger: DiscoveryLogger,
) -> Callable[[Envelope, FlowKey], None]:
    def write(envelope: Envelope, key: FlowKey) -> None:
        try:
            discovery_logger.log(envelope, direction_of(key))
        except OSError as error:
            raise CaptureAborted(str(error)) from error

    return write


def _capture_into(
    discovery_logger: DiscoveryLogger, interface: str | None, capture: CaptureFunction
) -> int:
    pipeline = PacketPipeline(_envelope_callback(discovery_logger))
    try:
        capture(pipeline, interface)
    except KeyboardInterrupt:
        print(f"Arrêt. {discovery_logger.logged_count} messages journalisés.")
        return EXIT_OK
    except CaptureAborted as error:
        return _fail(f"Écriture du journal impossible ({error}) après {discovery_logger.logged_count} messages.")
    # scapy raises several unrelated types when Npcap or the interface is unusable.
    except Exception as error:
        logger.debug("capture failure", exc_info=True)
        return _fail(f"Capture impossible ({error}). Vérifiez Npcap, le nom de "
                     "l'interface, et essayez un terminal administrateur.")
    return EXIT_OK


def _discover(interface: str | None, output: str, capture: CaptureFunction) -> int:
    try:
        discovery_logger = DiscoveryLogger(output)
    except OSError as error:
        return _fail(f"Impossible d'écrire le journal {output} : {error}")
    print(f"Journal écrit dans {output}. Ctrl+C pour arrêter.")
    try:
        return _capture_into(discovery_logger, interface, capture)
    finally:
        discovery_logger.close()


def run(argv: list[str] | None, capture: CaptureFunction) -> int:
    """Run the CLI with an injectable capture function."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "discover":
        return _discover(arguments.interface, arguments.output, capture)
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
