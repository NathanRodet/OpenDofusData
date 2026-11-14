"""CLI command recipes-update: one-off download of the craft recipes (DofusDB)."""

import argparse
import time
from pathlib import Path

from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.names_build import NamesFetchError, write_csv_atomically
from opendofusdata.names_fetch import (
    PAGE_SIZE,
    REQUEST_DELAY_SECONDS,
    FetchJson,
    Requester,
    Sleep,
    collect_all,
    http_get_json,
)
from opendofusdata.recipes_csv import DEFAULT_RECIPES_PATH, RECIPES_CSV_HEADER, build_recipes, recipe_rows

RECIPES_PATH = "/recipes"
RECIPES_SELECT = "&$select[]=resultId&$select[]=ingredientIds&$select[]=quantities"
INTERRUPTED_MESSAGE = "Interrompu, aucun fichier modifié."
UPDATE_NOTICE = ("Cette commande contacte api.dofusdb.fr une seule fois pour télécharger les recettes de craft "
                 "(environ 100 requêtes). La capture, elle, reste hors ligne.")


def add_recipes_command(commands: argparse._SubParsersAction) -> None:
    """Register recipes-update."""
    update = commands.add_parser("recipes-update", help="télécharge les recettes de craft (DofusDB)")
    update.add_argument("--output", default=DEFAULT_RECIPES_PATH,
                        help=f"fichier CSV à écrire (défaut : {DEFAULT_RECIPES_PATH})")


def download_recipes(output: Path, fetch: FetchJson = http_get_json, request_delay: float = REQUEST_DELAY_SECONDS,
                     sleep: Sleep = time.sleep) -> int:
    """Download every recipe and write the CSV atomically; returns how many recipes were written."""
    requester = Requester(fetch, sleep, request_delay)
    raw = collect_all(requester, RECIPES_PATH, RECIPES_SELECT, PAGE_SIZE, print)
    recipes = build_recipes(raw)
    write_csv_atomically(RECIPES_CSV_HEADER, recipe_rows(recipes), output)
    return len(recipes)


def recipes_update_command(arguments: argparse.Namespace, fetch: FetchJson = http_get_json,
                           request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep) -> int:
    """Download the recipes (a command that uses the network, like names-update)."""
    print(UPDATE_NOTICE)
    try:
        count = download_recipes(Path(arguments.output), fetch, request_delay, sleep)
    except NamesFetchError as error:
        return fail(str(error))
    except KeyboardInterrupt:
        return fail(INTERRUPTED_MESSAGE)
    print(f"{count} recettes écrites dans {arguments.output}.")
    return EXIT_OK
