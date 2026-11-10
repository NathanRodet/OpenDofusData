"""Item-name index (id -> French name) loaded from the local CSV: pure, no network."""

import csv
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_NAMES_PATH = "data/items.csv"
ITEMS_CSV_HEADER = ("id", "name_fr", "level", "type_fr")


@dataclass(frozen=True)
class ItemEntry:
    """One item of the index."""

    item_id: int
    name: str
    level: int | None
    type_name: str


def _parse_row(row: list[str]) -> ItemEntry:
    item_id, name, level, type_name = row
    if not name.strip():
        raise ValueError("nom vide")
    return ItemEntry(int(item_id), name, int(level) if level else None, type_name)


def _read_entries(path: Path) -> list[ItemEntry]:
    entries: list[ItemEntry] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            try:
                entries.append(_parse_row(row))
            except ValueError as error:
                logger.warning("ligne %d du fichier de noms ignorée (%s)", reader.line_num, error)
    return entries


class ItemNames:
    """In-memory index of item names with accent-insensitive search."""

    def __init__(self, entries: Iterable[ItemEntry] = ()) -> None:
        self._names = {entry.item_id: entry.name for entry in entries}

    @classmethod
    def load(cls, path: str | Path) -> "ItemNames":
        """Load the CSV file; a missing file gives an empty index."""
        file_path = Path(path)
        if not file_path.is_file():
            return cls()
        try:
            return cls(_read_entries(file_path))
        except (OSError, UnicodeError, csv.Error) as error:
            logger.warning("fichier de noms illisible, index vide (%s : %s)", file_path, error)
            return cls()

    def __len__(self) -> int:
        return len(self._names)

    def name_of(self, item_id: int) -> str | None:
        """Return the French name of an item id, or None when unknown."""
        return self._names.get(item_id)
