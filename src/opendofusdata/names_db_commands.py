"""CLI commands names-import and names-gaps: item names inside the database."""

import argparse
import sqlite3

from opendofusdata.capture_errors import EXIT_OK, fail
from opendofusdata.commands import check_database_path, format_table, with_store
from opendofusdata.game_servers import DEFAULT_SERVERS_PATH, GameServer, load_servers
from opendofusdata.item_names import DEFAULT_NAMES_PATH, ItemNames
from opendofusdata.names_db import (
    UnknownItem,
    count_items,
    count_servers,
    replace_items,
    unknown_items,
)
from opendofusdata.storage import PriceStore

DEFAULT_DATABASE = "prices.db"
GAP_LISTING_LIMIT = 20
GAP_HEADERS = ("id", "relevés lots", "relevés stats", "premier relevé", "dernier relevé")
DEV_RUN = r".\dev.ps1 run"
NO_NAMES_MESSAGE = ("Fichier de noms absent ou vide : {path}. "
                    f"Télécharge-le d'abord avec : {DEV_RUN} names-update")
NO_SERVERS_NOTE = ("Liste des serveurs absente ou illisible : seuls les objets sont importés. "
                   f"Pour la télécharger : {DEV_RUN} servers-update")
NOT_IMPORTED_MESSAGE = ("La table des noms est vide : aucun nom n'a encore été importé. "
                        f"Lance : {DEV_RUN} names-import")
NO_GAP_MESSAGE = "Aucun identifiant sans nom : tous les objets de la base ont un nom."


def add_names_db_commands(commands: argparse._SubParsersAction) -> None:
    """Register names-import and names-gaps."""
    importer = commands.add_parser("names-import", help="importe les noms d'objets dans la base")
    importer.add_argument("--db", default=DEFAULT_DATABASE, help="base SQLite (défaut : prices.db)")
    importer.add_argument("--names", default=DEFAULT_NAMES_PATH,
                          help=f"fichier CSV des noms (défaut : {DEFAULT_NAMES_PATH})")
    importer.add_argument("--servers", default=DEFAULT_SERVERS_PATH,
                          help=f"fichier CSV des serveurs (défaut : {DEFAULT_SERVERS_PATH})")
    gaps = commands.add_parser("names-gaps", help="liste les objets de la base sans nom")
    gaps.add_argument("--db", default=DEFAULT_DATABASE, help="base SQLite (défaut : prices.db)")


def _gap_line(gap: UnknownItem) -> str:
    return f"{gap.item_id} ({gap.row_count} relevés)"


def _print_import_summary(imported: int, gaps: list[UnknownItem]) -> None:
    print(f"{imported} objets importés dans la table items.")
    if not gaps:
        print("Aucun identifiant de la base n'est absent de la référence.")
        return
    print(f"{len(gaps)} identifiant(s) de la base absent(s) de la référence (affichés N/A) :")
    print(", ".join(_gap_line(gap) for gap in gaps[:GAP_LISTING_LIMIT]))
    if len(gaps) > GAP_LISTING_LIMIT:
        print(f"... et {len(gaps) - GAP_LISTING_LIMIT} autre(s) (voir : names-gaps).")


def _import_into(store: PriceStore, names: ItemNames, servers: list[GameServer]) -> int:
    imported = replace_items(store.connection, names.entries(), servers or None)
    _print_import_summary(imported, unknown_items(store.connection))
    if servers:
        print(f"{count_servers(store.connection)} serveurs importés dans la table servers.")
    else:
        print(NO_SERVERS_NOTE)
    return EXIT_OK


def names_import_command(arguments: argparse.Namespace) -> int:
    """Replace the items table with the content of the names file."""
    problem = check_database_path(arguments.db)
    if problem is not None:
        return fail(problem)
    names = ItemNames.load(arguments.names)
    if len(names) == 0:
        return fail(NO_NAMES_MESSAGE.format(path=arguments.names))
    servers = load_servers(arguments.servers)
    return with_store(arguments, lambda store: _import_into(store, names, servers))


def _print_gaps(store: PriceStore) -> int:
    if count_items(store.connection) == 0:
        print(NOT_IMPORTED_MESSAGE)
        return EXIT_OK
    gaps = unknown_items(store.connection)
    if not gaps:
        print(NO_GAP_MESSAGE)
        return EXIT_OK
    rows = [(gap.item_id, gap.lot_price_rows, gap.stats_rows, gap.first_seen, gap.last_seen)
            for gap in gaps]
    print(format_table(GAP_HEADERS, rows))
    return EXIT_OK


def names_gaps_command(arguments: argparse.Namespace) -> int:
    """Print the item ids present in the database but missing from the names table."""
    return with_store(arguments, _print_gaps)
