"""What a craft costs and earns: pure logic."""

from collections.abc import Callable
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
