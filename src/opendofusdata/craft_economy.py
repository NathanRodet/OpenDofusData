"""What a craft costs and earns: pure logic."""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from opendofusdata.recipes_csv import Recipe

PERCENT = 100


@dataclass(frozen=True)
class CraftRow:
    """One craft: sale price, resources cost (None when a resource has no price) and the margin."""

    item_id: int
    sale_price: float | None
    cost: float | None
    margin: float | None
    margin_percent: float | None
    ingredients: tuple[tuple[int, int, float | None], ...]


def _cost_of(ingredients: tuple[tuple[int, int, float | None], ...]) -> float | None:
    if any(price is None for _, _, price in ingredients):
        return None
    return sum(price * quantity for _, quantity, price in ingredients)


def craft_row(recipe: Recipe, sale_price: float | None, ingredient_price: Callable[[int], float | None]) -> CraftRow:
    """Price a recipe; the margin is known only when the sale price and every resource price are."""
    ingredients = tuple((item, quantity, ingredient_price(item)) for item, quantity in recipe.ingredients)
    cost = _cost_of(ingredients)
    if cost is None or sale_price is None:
        return CraftRow(recipe.result_id, sale_price, cost, None, None, ingredients)
    margin = sale_price - cost
    percent = margin * PERCENT / cost if cost else None
    return CraftRow(recipe.result_id, sale_price, cost, margin, percent, ingredients)


def _missing_of(row: CraftRow) -> list[int]:
    missing = [item for item, _, price in row.ingredients if price is None]
    return missing + ([row.item_id] if row.sale_price is None else [])


def missing_prices(rows: Iterable[CraftRow], limit: int) -> list[tuple[int, int]]:
    """The items without a price that block the most crafts, as (item id, blocked crafts), most blocking first."""
    counts = Counter(item for row in rows for item in _missing_of(row))
    return sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
