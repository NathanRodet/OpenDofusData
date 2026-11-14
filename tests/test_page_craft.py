"""Headless-safe checks of the Craft page on synthetic data."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.effects_csv import (EFFECTS_CSV_HEADER, EFFECTS_FILE, RUNES_CSV_HEADER, RUNES_FILE,
                                       ItemEffects, Rune, StatLine, effects_rows, runes_rows)
from opendofusdata.names_build import write_csv_atomically
from opendofusdata.page_craft import CraftPage
from opendofusdata.records import LotPrice
from opendofusdata.recipes_csv import DEFAULT_RECIPES_FILE, RECIPES_CSV_HEADER, Recipe, recipe_rows
from tests.view_page_helpers import NOW, make_context, open_store

HAT, WOOD, STONE, VIT_RUNE = 100, 200, 201, 1523
NAMES = {HAT: "Chapeau", WOOD: "Bois", STONE: "Pierre", VIT_RUNE: "Rune Vi"}
STAMP = "2026-11-12T09:00:00Z"


def context_with_data(tmp_path):
    context = make_context(tmp_path, NAMES)
    context.data_directory = tmp_path
    write_csv_atomically(RECIPES_CSV_HEADER, recipe_rows([Recipe(HAT, ((WOOD, 2), (STONE, 1)))]),
                         tmp_path / DEFAULT_RECIPES_FILE)
    item = ItemEffects(HAT, 20, (StatLine(125, 16, 20),))
    write_csv_atomically(EFFECTS_CSV_HEADER, effects_rows([item]), tmp_path / EFFECTS_FILE)
    write_csv_atomically(RUNES_CSV_HEADER, runes_rows([Rune(VIT_RUNE, 125, 5, 0.2)]), tmp_path / RUNES_FILE)
    return context


def fill(store, with_stone: bool = True) -> None:
    prices = {HAT: 1000, WOOD: 100, VIT_RUNE: 50}
    prices.update({STONE: 300} if with_stone else {})
    for item_id, price in prices.items():
        store.save_lot_price(LotPrice(item_id, "Brial", 1, price, STAMP))


def test_craft_lists_the_priced_craft_with_its_margin(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = CraftPage(root, context_with_data(tmp_path), clock=lambda: NOW)
    page.refresh()
    assert [row.cells[:5] for row in page.table._shown] == [("Chapeau", "1 000", "500", "+500", "+100 %")]
    store.close()


def test_craft_names_the_missing_price_when_nothing_is_selected(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store, with_stone=False)
    page = CraftPage(root, context_with_data(tmp_path), clock=lambda: NOW)
    page.refresh()
    assert page.table._shown == [] and any("Pierre" in label for label, _, _ in page.ingredients_list.rows)
    store.close()
