"""What the Brisage page shows: one row per broken object with its value and plus-value."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from opendofusdata.breaking_economy import RunesValue, object_value, plus_value, runes_value
from opendofusdata.breaking_store import broken_items
from opendofusdata.item_labels import ItemLabeler
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST
from opendofusdata.records import BrokenItem
from opendofusdata.time_filters import Window, parse_stored, stored_bounds


@dataclass(frozen=True)
class BreakingRow:
    """One broken object: its coefficient, runes and the three values compared on the page."""

    moment: datetime
    item_id: int
    name: str
    quantity: int
    coefficient: float
    runes: tuple[tuple[int, int], ...]
    estimated_value: float | None
    hdv_value: float | None
    runes_value: RunesValue
    plus_value: float | None


def _estimated_unit_price(book: PriceBook, item_id: int) -> float | None:
    prices = book.prices_of(item_id)
    return None if prices is None or prices.mean_24h is None else float(prices.mean_24h)


def _row_of(broken: BrokenItem, name_of: ItemLabeler, book: PriceBook, mode: str) -> BreakingRow:
    value = runes_value(broken.runes, lambda rune_id: book.unit_price(rune_id, mode))
    listed = book.unit_price(broken.item_id, PRICE_LAST)  # the cheapest listing
    hdv_value = object_value(listed if listed is not None else book.last_sale(broken.item_id), broken.quantity)
    return BreakingRow(
        parse_stored(broken.captured_at), broken.item_id, name_of(broken.item_id), broken.quantity,
        broken.coefficient, broken.runes,
        object_value(_estimated_unit_price(book, broken.item_id), broken.quantity), hdv_value, value,
        plus_value(value, hdv_value))


def _plus_value_order(row: BreakingRow) -> tuple[bool, float]:
    return (row.plus_value is None, -(row.plus_value or 0.0))


def breaking_rows(connection: sqlite3.Connection, server: str, window: Window, name_of: ItemLabeler,
                  book: PriceBook, mode: str) -> list[BreakingRow]:
    """The objects broken on the server inside the window, best plus-value first, unknown last."""
    low, high = stored_bounds(window)
    rows = [_row_of(broken, name_of, book, mode) for broken in broken_items(connection)
            if broken.server == server and low <= broken.captured_at <= high]
    return sorted(rows, key=_plus_value_order)

