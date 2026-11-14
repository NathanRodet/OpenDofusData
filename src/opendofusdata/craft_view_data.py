"""Craft rows read from the price book and the recipes: read-only."""

import sqlite3
from collections.abc import Sequence

from opendofusdata.craft_economy import CraftRow, craft_row
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST, best_lot_unit_price
from opendofusdata.recipes_csv import Recipe


def craft_rows(connection: sqlite3.Connection, server: str, recipes: Sequence[Recipe]) -> list[CraftRow]:
    """Every recipe priced with the latest known prices; sorted by margin, best first, unpriced last."""
    book = PriceBook.load(connection, server)
    rows = [craft_row(recipe, book.unit_price(recipe.result_id, PRICE_LAST),
                      lambda item: best_lot_unit_price(book.prices_of(item))) for recipe in recipes]
    return sorted(rows, key=lambda row: (row.margin is None, -(row.margin or 0)))
