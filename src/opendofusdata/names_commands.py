"""CLI command names-update: one-off download of the item-name index."""

import argparse
import time
from pathlib import Path

from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.item_names import DEFAULT_NAMES_PATH
from opendofusdata.names_db_commands import add_names_db_commands
from opendofusdata.names_build import NamesFetchError
from opendofusdata.names_fetch import (
    REQUEST_DELAY_SECONDS,
    FetchJson,
    FetchSummary,
    Sleep,
    download_item_names,
    http_get_json,
)

INTERRUPTED_MESSAGE = "Interrompu, aucun fichier modifié."
UPDATE_NOTICE = (
    "Cette commande contacte api.dofusdb.fr une seule fois pour télécharger les noms d'objets "
    "(environ 430 requêtes, quelques dizaines de secondes). La capture, elle, reste hors ligne."
)


def add_names_commands(commands: argparse._SubParsersAction) -> None:
    """Register names-update, names-import and names-gaps."""
    add_names_db_commands(commands)
    update = commands.add_parser("names-update", help="télécharge l'index des noms d'objets (DofusDB)")
    update.add_argument("--output", default=DEFAULT_NAMES_PATH,
                        help=f"fichier CSV à écrire (défaut : {DEFAULT_NAMES_PATH})")


def _print_summary(summary: FetchSummary, seconds: float) -> None:
    print(f"{summary.rows} objets écrits dans {summary.path} ({summary.size_bytes} octets, "
          f"{seconds:.0f} s), {summary.skipped} ignoré(s) sans nom, "
          f"{summary.duplicates} doublon(s).")


def names_update_command(
    arguments: argparse.Namespace, fetch: FetchJson = http_get_json,
    request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep,
) -> int:
    """Download the item-name index (the only command that uses the network)."""
    print(UPDATE_NOTICE)
    started = time.monotonic()
    try:
        summary = download_item_names(Path(arguments.output), fetch, request_delay=request_delay,
                                      sleep=sleep)
    except NamesFetchError as error:
        return fail(str(error))
    except KeyboardInterrupt:
        return fail(INTERRUPTED_MESSAGE)
    _print_summary(summary, time.monotonic() - started)
    return EXIT_OK
