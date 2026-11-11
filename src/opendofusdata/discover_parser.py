"""Argument parser of the discover command (kept apart from cli.py to keep both small)."""

import argparse

from opendofusdata.discovery import MAX_FIELDS_PER_MESSAGE, parse_hex_types, parse_max_fields

DEFAULT_OUTPUT = "captures/discovery.jsonl"


def add_discover_command(commands: argparse._SubParsersAction) -> None:
    """Register the discover command."""
    discover = commands.add_parser("discover", help="journalise la structure des messages")
    discover.add_argument("--interface", default=None, help="interface réseau à écouter")
    discover.add_argument("--output", default=DEFAULT_OUTPUT, help="fichier de log JSON Lines")
    discover.add_argument("--include-text", action="store_true",
                          help="inclut des aperçus texte/hex (données personnelles possibles)")
    discover.add_argument("--hex-types", type=parse_hex_types, default=frozenset(), metavar="NAMES",
                          help="types de message (ex. jzs,ire) avec aperçu hex de leurs octets "
                               "(données personnelles possibles)")
    discover.add_argument("--max-fields", type=parse_max_fields, default=MAX_FIELDS_PER_MESSAGE, metavar="N",
                          help=f"champs décrits par message (défaut : {MAX_FIELDS_PER_MESSAGE}); "
                               "augmente-le pour lire une grande liste comme l'inventaire")
