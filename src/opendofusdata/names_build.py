"""Turns raw DofusDB items into sanitised index entries and writes the CSV: no network."""

import math
import csv
import os
import tempfile
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from opendofusdata.item_names import ITEMS_CSV_HEADER, ItemEntry

MAX_NAME_LENGTH = 120
CONTROL_CATEGORY_PREFIX = "C"
UNEXPECTED_SHAPE_MESSAGE = "Réponse inattendue de l'API DofusDB ({detail})."


class NamesFetchError(Exception):
    """A download or build problem, with a message meant for the user (French)."""


@dataclass(frozen=True)
class BuildResult:
    """Entries ready to write, plus what was left out."""

    entries: list[ItemEntry]
    skipped: int
    duplicates: int


def clean_name(text: str) -> str:
    """Drop control characters, collapse whitespace and cap the length."""
    spaced = "".join(" " if char.isspace() else char for char in text)
    printable = "".join(char for char in spaced
                        if not unicodedata.category(char).startswith(CONTROL_CATEGORY_PREFIX))
    return " ".join(printable.split())[:MAX_NAME_LENGTH].strip()


def require_id(raw: object) -> int:
    identifier = raw.get("id") if isinstance(raw, dict) else None
    if not isinstance(identifier, int) or isinstance(identifier, bool):
        raise NamesFetchError(UNEXPECTED_SHAPE_MESSAGE.format(detail="entrée sans identifiant"))
    return identifier


def localized_name(raw: dict, language: str) -> str:
    names = raw.get("name")
    value = names.get(language) if isinstance(names, dict) else None
    return clean_name(value) if isinstance(value, str) else ""


def build_type_names(raw_types: list[object]) -> dict[int, str]:
    """Map each item type id to its French name."""
    return {require_id(raw): localized_name(raw, "fr") for raw in raw_types}


def _level_of(raw: dict) -> int | None:
    level = raw.get("level")
    return level if isinstance(level, int) and not isinstance(level, bool) else None


def _recycling_rate_of(raw: dict) -> float | None:
    """The recyclingNuggets of an item when it is a finite, non-negative number."""
    rate = raw.get("recyclingNuggets")
    valid = isinstance(rate, (int, float)) and not isinstance(rate, bool) and math.isfinite(rate) and rate >= 0
    return float(rate) if valid else None


def _type_name_of(raw: dict, type_names: dict[int, str]) -> str:
    type_id = raw.get("typeId")
    return type_names.get(type_id, "") if isinstance(type_id, int) else ""


def build_entries(raw_items: list[object], type_names: dict[int, str]) -> BuildResult:
    """Build entries sorted by id: French name, else English, else skipped; first id wins."""
    entries: dict[int, ItemEntry] = {}
    skipped = duplicates = 0
    for raw in raw_items:
        identifier = require_id(raw)
        name = localized_name(raw, "fr") or localized_name(raw, "en")
        if identifier in entries:
            duplicates += 1
        elif not name:
            skipped += 1
        else:
            entries[identifier] = ItemEntry(identifier, name, _level_of(raw),
                                            _type_name_of(raw, type_names), _recycling_rate_of(raw))
    return BuildResult([entries[key] for key in sorted(entries)], skipped, duplicates)


def _write_rows(file, rows: Iterable[Sequence[object]]) -> None:
    writer = csv.writer(file, lineterminator="\n")
    writer.writerows(rows)


def _discard(temporary: str | None) -> None:
    if temporary is not None:
        Path(temporary).unlink(missing_ok=True)


def write_csv_atomically(header: Sequence[str], rows: Iterable[Sequence[object]],
                         path: Path) -> None:
    """Write the CSV to a temp file next to the target, then rename it atomically.

    The temp file is removed on any failure, including Ctrl+C.
    """
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            _write_rows(file, chain([header], rows))
        os.replace(temporary, path)
    except OSError as error:
        _discard(temporary)
        raise NamesFetchError(f"Impossible d'écrire {path} : {error}") from error
    except BaseException:
        _discard(temporary)
        raise


def write_items_csv(entries: list[ItemEntry], path: Path) -> None:
    """Write the item index CSV atomically."""
    rows = [(entry.item_id, entry.name, "" if entry.level is None else entry.level, entry.type_name,
             "" if entry.recycling_nuggets is None else repr(entry.recycling_nuggets)) for entry in entries]
    write_csv_atomically(ITEMS_CSV_HEADER, rows, path)
