"""Command-line entry point: the discovery mode."""

import argparse
import logging
import sys
from collections.abc import Callable

from dofus_prices.capture import PacketPipeline, direction_of, run_capture
from dofus_prices.discovery import DiscoveryLogger

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "captures/discovery.jsonl"
EXIT_OK = 0
EXIT_CAPTURE_FAILED = 1
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


def _discover(interface: str | None, output: str, capture: CaptureFunction) -> int:
    discovery_logger = DiscoveryLogger(output)
    pipeline = PacketPipeline(
        lambda envelope, key: discovery_logger.log(envelope, direction_of(key))
    )
    print(f"Journal écrit dans {output}. Ctrl+C pour arrêter.")
    try:
        capture(pipeline, interface)
    except KeyboardInterrupt:
        print(f"Arrêt. {discovery_logger.logged_count} messages journalisés.")
        return EXIT_OK
    except (ImportError, OSError) as error:
        logger.error("Capture impossible (%s).", error)
        print("Capture impossible : vérifiez Npcap et essayez un terminal administrateur.",
              file=sys.stderr)
        return EXIT_CAPTURE_FAILED
    finally:
        discovery_logger.close()
    return EXIT_OK


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
