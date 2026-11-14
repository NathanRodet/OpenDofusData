"""Item stat lines and rune definitions: parsing DofusDB data and reading/writing the two CSV files. No network."""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

EFFECTS_FILE = "item_effects.csv"
RUNES_FILE = "runes.csv"
EFFECTS_CSV_HEADER = ("item_id", "level", "lines")
RUNES_CSV_HEADER = ("rune_id", "action_id", "amount", "power_rate")
RUNE_TYPE_ID = 78
LINE_SEPARATOR = ";"
VALUE_SEPARATOR = ":"


@dataclass(frozen=True)
class StatLine:
    """One stat line of an item: its effect id and its roll range (equal bounds for a fixed value)."""

    action_id: int
    minimum: int
    maximum: int


@dataclass(frozen=True)
class ItemEffects:
    """The stat lines of an item and its level."""

    item_id: int
    level: int
    lines: tuple[StatLine, ...]


@dataclass(frozen=True)
class Rune:
    """A rune item: the stat it gives, how much of it, and the weight of that stat."""

    rune_id: int
    action_id: int
    amount: int
    power_rate: float


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def stat_line_of(raw: object) -> StatLine | None:
    """A stat line from one raw possible effect (the maximum is diceSide, or diceNum when the value is fixed)."""
    if not isinstance(raw, dict) or not _is_int(raw.get("actionId")) or not _is_int(raw.get("diceNum")):
        return None
    minimum, side = raw["diceNum"], raw.get("diceSide", 0)
    maximum = side if _is_int(side) and side > minimum else minimum
    return StatLine(raw["actionId"], minimum, maximum) if minimum > 0 else None


def item_effects_of(raw: object) -> ItemEffects | None:
    """The stat lines of one raw item; None for a rune, an item without level or without any stat line."""
    if not isinstance(raw, dict) or not _is_int(raw.get("id")) or not _is_int(raw.get("level")):
        return None
    if raw.get("typeId") == RUNE_TYPE_ID or raw["level"] <= 0:
        return None
    lines = tuple(line for line in map(stat_line_of, raw.get("possibleEffects") or []) if line)
    return ItemEffects(raw["id"], raw["level"], lines) if lines else None


def effects_rows(items: list[ItemEffects]) -> list[tuple[int, int, str]]:
    """The CSV rows of the item effects."""
    return [(item.item_id, item.level, LINE_SEPARATOR.join(
        VALUE_SEPARATOR.join(map(str, (line.action_id, line.minimum, line.maximum))) for line in item.lines))
        for item in items]


def runes_rows(runes: list[Rune]) -> list[tuple[int, int, int, float]]:
    """The CSV rows of the runes."""
    return [(rune.rune_id, rune.action_id, rune.amount, rune.power_rate) for rune in runes]


def _read_rows(path: str | Path) -> list[list[str]]:
    try:
        with open(path, encoding="utf-8", newline="") as file:
            return [row for row in list(csv.reader(file))[1:] if row]
    except FileNotFoundError:
        return []
    except OSError as error:
        logger.warning("fichier illisible %s (%s)", path, error)
        return []


def load_item_effects(path: str | Path) -> dict[int, ItemEffects]:
    """Read the item effects CSV, keyed by item id; unreadable rows are skipped with a warning."""
    items: dict[int, ItemEffects] = {}
    for row in _read_rows(path):
        try:
            lines = tuple(StatLine(*map(int, part.split(VALUE_SEPARATOR))) for part in row[2].split(LINE_SEPARATOR))
            items[int(row[0])] = ItemEffects(int(row[0]), int(row[1]), lines)
        except (ValueError, IndexError, TypeError):
            logger.warning("ligne d'effets illisible ignorée : %s", row)
    return items


def load_runes(path: str | Path) -> list[Rune]:
    """Read the runes CSV; unreadable rows are skipped with a warning."""
    runes = []
    for row in _read_rows(path):
        try:
            runes.append(Rune(int(row[0]), int(row[1]), int(row[2]), float(row[3])))
        except (ValueError, IndexError):
            logger.warning("ligne de rune illisible ignorée : %s", row)
    return runes
