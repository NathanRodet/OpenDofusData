"""CLI command effects-update: one-off download of item stat lines, runes and stat weights (DofusDB)."""

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.effects_csv import (
    EFFECTS_CSV_HEADER,
    EFFECTS_FILE,
    RUNE_TYPE_ID,
    RUNES_CSV_HEADER,
    RUNES_FILE,
    Rune,
    effects_rows,
    item_effects_of,
    runes_rows,
    stat_line_of,
)
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

ITEMS_SELECT = ("&$select[]=id&$select[]=level&$select[]=typeId&$select[]=possibleEffects.actionId"
                "&$select[]=possibleEffects.diceNum&$select[]=possibleEffects.diceSide")
EFFECTS_SELECT = "&$select[]=id&$select[]=effectPowerRate"
DEFAULT_DIRECTORY = "data"
INTERRUPTED_MESSAGE = "Interrompu, aucun fichier modifié."
UPDATE_NOTICE = ("Cette commande contacte api.dofusdb.fr une seule fois pour télécharger les effets des objets "
                 "(environ 450 requêtes, quelques minutes). La capture, elle, reste hors ligne.")


def add_effects_command(commands: argparse._SubParsersAction) -> None:
    """Register effects-update."""
    update = commands.add_parser("effects-update", help="télécharge les effets des objets et les runes (DofusDB)")
    update.add_argument("--directory", default=DEFAULT_DIRECTORY, help=f"dossier des CSV (défaut : {DEFAULT_DIRECTORY})")


def build_runes(raw_items: list[object], power_rates: dict[int, float]) -> list[Rune]:
    """The runes of the raw items: one stat line each, weighted by the power rate of its stat."""
    runes = []
    for raw in raw_items:
        if not isinstance(raw, dict) or raw.get("typeId") != RUNE_TYPE_ID or not isinstance(raw.get("id"), int):
            continue
        line = next(filter(None, map(stat_line_of, raw.get("possibleEffects") or [])), None)
        if line is not None:
            runes.append(Rune(raw["id"], line.action_id, line.minimum, power_rates.get(line.action_id, 0.0)))
    return sorted(runes, key=lambda rune: rune.rune_id)


def power_rates_of(raw_effects: list[object]) -> dict[int, float]:
    """Stat weight (effectPowerRate) by effect id."""
    return {raw["id"]: float(raw["effectPowerRate"]) for raw in raw_effects
            if isinstance(raw, dict) and isinstance(raw.get("id"), int)
            and isinstance(raw.get("effectPowerRate"), (int, float))}


def download_effects(directory: Path, fetch: FetchJson = http_get_json, request_delay: float = REQUEST_DELAY_SECONDS,
                     sleep: Sleep = time.sleep, progress: Callable[[str], None] = print) -> tuple[int, int]:
    """Download items and stat weights, write both CSV files; returns (items with effects, runes)."""
    requester = Requester(fetch, sleep, request_delay)
    raw_items = collect_all(requester, "/items", ITEMS_SELECT, PAGE_SIZE, progress)
    rates = power_rates_of(collect_all(requester, "/effects", EFFECTS_SELECT, PAGE_SIZE, progress))
    items = sorted(filter(None, map(item_effects_of, raw_items)), key=lambda item: item.item_id)
    runes = build_runes(raw_items, rates)
    write_csv_atomically(EFFECTS_CSV_HEADER, effects_rows(items), directory / EFFECTS_FILE)
    write_csv_atomically(RUNES_CSV_HEADER, runes_rows(runes), directory / RUNES_FILE)
    return len(items), len(runes)


def effects_update_command(arguments: argparse.Namespace, fetch: FetchJson = http_get_json,
                           request_delay: float = REQUEST_DELAY_SECONDS, sleep: Sleep = time.sleep) -> int:
    """Download the effects and runes (a command that uses the network, like names-update)."""
    print(UPDATE_NOTICE)
    try:
        items, runes = download_effects(Path(arguments.directory), fetch, request_delay, sleep)
    except NamesFetchError as error:
        return fail(str(error))
    except KeyboardInterrupt:
        return fail(INTERRUPTED_MESSAGE)
    print(f"{items} objets avec effets et {runes} runes écrits dans {arguments.directory}.")
    return EXIT_OK
