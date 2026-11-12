"""CLI command reset-data: empties the collected data after a backup."""

import argparse
import sqlite3
from collections.abc import Callable

from opendofusdata.app_config import default_config_path, load_config
from opendofusdata.capture_errors import EXIT_OK, EXIT_USAGE, fail
from opendofusdata.client_settings import choose_database_path, default_database_path
from opendofusdata.reset_data import collected_counts, reset_collected_data
from opendofusdata.run_pipeline import utc_now

CONFIRM_MESSAGE = ("Cette commande efface toutes les données collectées (prix, statistiques, brisages, "
                   "familiers) de {path}. Une sauvegarde est créée avant. Relance avec --yes pour confirmer.")
DONE_MESSAGE = "Sauvegarde : {backup}\nLignes supprimées : {counts}"
FAILED_MESSAGE = "Remise à zéro impossible ({error})."


def add_reset_command(commands: argparse._SubParsersAction) -> None:
    """Register the reset-data command."""
    parser = commands.add_parser("reset-data", help="efface les données collectées (avec sauvegarde)")
    parser.add_argument("--db", default=None, help="base SQLite (défaut : celle des réglages)")
    parser.add_argument("--yes", action="store_true", help="confirme l'effacement")


def reset_data_command(arguments: argparse.Namespace) -> int:
    """Back the database up and remove the collected rows; nothing changes without --yes."""
    database = choose_database_path(arguments.db, load_config(default_config_path()), default_database_path())
    if not arguments.yes:
        print(CONFIRM_MESSAGE.format(path=database))
        return EXIT_USAGE
    try:
        counts = collected_counts(database)
        backup = reset_collected_data(database, utc_now().astimezone())
    except (OSError, sqlite3.Error) as error:
        return fail(FAILED_MESSAGE.format(error=error))
    print(DONE_MESSAGE.format(backup=backup, counts=", ".join(f"{table} {count}" for table, count in counts.items())))
    return EXIT_OK


RESET_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"reset-data": reset_data_command}
