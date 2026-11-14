"""Theoretical breaking rows: item stat lines, HDV prices and the runes the formula expects. Read-only."""

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from opendofusdata.breaking_theory import base_runes_by_action, expected_runes
from opendofusdata.breaking_view_data import breaking_rows
from opendofusdata.effects_csv import ItemEffects, Rune
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST, PRICE_MEAN
from opendofusdata.time_filters import Window

UNBOUNDED: Window = (None, None)
DEFAULT_COEFFICIENT = 0.5


@dataclass(frozen=True)
class TheoryRow:
    """One object: HDV price, the coefficient used, the expected runes and what real breakings gave."""

    item_id: int
    hdv_price: float
    coefficient: float
    observed: bool
    runes: tuple[tuple[int, float, float | None], ...]
    runes_value: float
    plus_value: float
    real_runes_value: float | None
    breakings: int


def rune_price(book: PriceBook, rune_id: int) -> float | None:
    """The average rune price, else the cheapest listing."""
    price = book.unit_price(rune_id, PRICE_MEAN)
    return price if price is not None else book.unit_price(rune_id, PRICE_LAST)


def _observed(connection: sqlite3.Connection, server: str, book: PriceBook,
              name_of: Callable[[int], str]) -> dict[int, tuple[float, float | None, int]]:
    """Per object: mean coefficient, mean runes value (None when unknown) and breaking count."""
    grouped: dict[int, list] = {}
    for row in breaking_rows(connection, server, UNBOUNDED, name_of, book, PRICE_MEAN):
        grouped.setdefault(row.item_id, []).append(row)
    return {item: (sum(r.coefficient for r in rows) / len(rows),
                   _mean_value([r.runes_value.total for r in rows]), len(rows)) for item, rows in grouped.items()}


def _mean_value(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def theory_rows(connection: sqlite3.Connection, server: str, effects: Mapping[int, ItemEffects], runes: list[Rune],
                typed: Mapping[int, float], name_of: Callable[[int], str]) -> list[TheoryRow]:
    """A row for every object with a known HDV price and at least one rune; best plus-value first."""
    book, base = PriceBook.load(connection, server), base_runes_by_action(runes)
    observed = _observed(connection, server, book, name_of)
    rows = [row for item in effects.values()
            if (row := _row_of(item, book, base, observed.get(item.item_id), typed.get(item.item_id))) is not None]
    return sorted(rows, key=lambda row: -row.plus_value)


def _row_of(item: ItemEffects, book: PriceBook, base: Mapping[int, Rune],
            seen: tuple[float, float | None, int] | None, typed: float | None) -> TheoryRow | None:
    price = book.unit_price(item.item_id, PRICE_LAST)
    if price is None:
        return None
    coefficient = typed if typed is not None else (seen[0] if seen else DEFAULT_COEFFICIENT)
    lines = [(rune_id, count, rune_price(book, rune_id)) for rune_id, count in expected_runes(item, coefficient, base)]
    if not lines:
        return None
    value = sum(count * unit for _, count, unit in lines if unit is not None)
    return TheoryRow(item.item_id, price, coefficient, seen is not None and typed is None, tuple(lines), value,
                     value - price, seen[1] if seen else None, seen[2] if seen else 0)
