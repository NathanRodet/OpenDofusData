"""Recipes parsing, craft margins and the recipes download (synthetic data)."""

import argparse

from opendofusdata.craft_economy import craft_row
from opendofusdata.price_rules import ItemPrices, best_lot_unit_price
from opendofusdata.recipes_commands import recipes_update_command
from opendofusdata.recipes_csv import Recipe, build_recipes, load_recipes, recipe_rows

RAW = [
    {"resultId": 44, "ingredientIds": [16512, 303], "quantities": [3, 3]},
    {"resultId": 44, "ingredientIds": [1], "quantities": [1]},
    {"resultId": 7, "ingredientIds": [5], "quantities": [0]},
    {"resultId": 9, "ingredientIds": [5, 6], "quantities": [1]},
    "junk",
]


def test_build_recipes_keeps_valid_first_recipe_sorted() -> None:
    assert build_recipes(RAW) == [Recipe(44, ((16512, 3), (303, 3)))]


def test_csv_round_trip(tmp_path) -> None:
    path = tmp_path / "recipes.csv"
    path.write_text("result_id,ingredients\n" + "\n".join(f"{a},{b}" for a, b in recipe_rows(build_recipes(RAW))) + "\n",
                    encoding="utf-8")
    assert load_recipes(path) == [Recipe(44, ((16512, 3), (303, 3)))]
    assert load_recipes(tmp_path / "missing.csv") == []


def test_margin_needs_every_price() -> None:
    recipe = Recipe(1, ((10, 2), (11, 1)))
    prices = {10: 100.0, 11: 50.0}
    row = craft_row(recipe, 400.0, prices.get)
    assert (row.cost, row.margin, row.margin_percent) == (250.0, 150.0, 60.0)
    assert craft_row(recipe, 400.0, {10: 100.0}.get).margin is None
    assert craft_row(recipe, None, prices.get).margin is None


def test_best_unit_price_uses_the_cheapest_lot() -> None:
    prices = ItemPrices({1: 100, 100: 7000, 1000: 60000}, None, None)
    assert best_lot_unit_price(prices) == 60.0
    assert best_lot_unit_price(None) is None


def test_recipes_update_writes_the_csv(tmp_path) -> None:
    page = {"total": 1, "limit": 50, "skip": 0, "data": RAW[:1]}
    output = tmp_path / "out.csv"
    assert recipes_update_command(argparse.Namespace(output=str(output)), lambda url: page, 0, lambda s: None) == 0
    assert load_recipes(output) == [Recipe(44, ((16512, 3), (303, 3)))]


def test_missing_prices_rank_the_items_blocking_most_crafts() -> None:
    from opendofusdata.craft_economy import missing_prices

    prices = {10: 5.0}
    rows = [craft_row(Recipe(1, ((10, 1), (11, 1))), 9.0, prices.get),
            craft_row(Recipe(2, ((11, 2), (12, 1))), None, prices.get)]
    assert missing_prices(rows, 3) == [(11, 2), (2, 1), (12, 1)]
