"""Headless-safe checks of the Craft page on synthetic data."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.effects_csv import (EFFECTS_CSV_HEADER, EFFECTS_FILE, RUNES_CSV_HEADER, RUNES_FILE,
                                       ItemEffects, Rune, StatLine, effects_rows, runes_rows)
from opendofusdata.names_build import write_csv_atomically
from opendofusdata.page_craft import CraftPage
from opendofusdata.pet_favorites_store import CRAFT_FAVORITES_KEY
from opendofusdata.records import LotPrice
from opendofusdata.value_format import UNKNOWN_TEXT
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


CAPE, FEATHER = 300, 202


def two_crafts_context(tmp_path):
    """HAT is fully priced; CAPE needs a feather nobody priced."""
    context = make_context(tmp_path, {**NAMES, CAPE: "Cape", FEATHER: "Plume"})
    context.data_directory = tmp_path
    recipes = [Recipe(HAT, ((WOOD, 2), (STONE, 1))), Recipe(CAPE, ((WOOD, 1), (FEATHER, 1)))]
    write_csv_atomically(RECIPES_CSV_HEADER, recipe_rows(recipes), tmp_path / DEFAULT_RECIPES_FILE)
    return context


def shown_names(page: CraftPage) -> list[str]:
    return [row.cells[0] for row in page.table._shown]


def open_page(root, tmp_path) -> CraftPage:
    store = open_store(tmp_path)
    fill(store)
    store.save_lot_price(LotPrice(CAPE, "Brial", 1, 800, STAMP))
    store.close()
    page = CraftPage(root, two_crafts_context(tmp_path), clock=lambda: NOW)
    page.refresh()
    return page


def test_incomplete_crafts_are_hidden_by_default_and_shown_with_the_checkbox(root, tmp_path) -> None:
    page = open_page(root, tmp_path)
    assert shown_names(page) == ["Chapeau"]
    page.incomplete_box.select()
    page.refresh()
    assert shown_names(page) == ["Chapeau", "Cape"]  # complete first, incomplete last
    cape = page.table._shown[1]
    assert cape.cells[1] == "800"
    assert cape.cells[3] == UNKNOWN_TEXT  # no margin: shown as unknown, nothing crashes


def test_an_incomplete_craft_names_what_is_missing_in_its_detail(root, tmp_path) -> None:
    page = open_page(root, tmp_path)
    page.incomplete_box.select()
    page.refresh()
    page._selected = CAPE
    page._refresh_detail()
    labels = [(label, value) for label, value, _ in page.ingredients_list.rows]
    assert ("Plume ×1", "prix inconnu") in labels
    assert any(label.startswith("Prix") and value != "" for label, value in labels)


def test_a_favorite_craft_stays_visible_even_incomplete_and_is_marked(root, tmp_path) -> None:
    page = open_page(root, tmp_path)
    page.incomplete_box.select()
    page.refresh()
    page._selected = CAPE
    page._refresh_detail()
    page.favorite_box.select()
    page._toggle_favorite()
    page.incomplete_box.deselect()
    page.refresh()
    assert shown_names(page) == ["Chapeau", "★ Cape"]


def test_favorites_only_keeps_just_the_favorites(root, tmp_path) -> None:
    page = open_page(root, tmp_path)
    page._selected = HAT
    page._refresh_detail()
    page.favorite_box.select()
    page._toggle_favorite()
    page.favorites_only.select()
    page.refresh()
    assert shown_names(page) == ["★ Chapeau"]
    page.favorite_box.deselect()  # unticking the box removes the favorite
    page._toggle_favorite()
    page.refresh()
    assert shown_names(page) == []


def test_craft_favorites_do_not_touch_the_pet_favorites(root, tmp_path) -> None:
    from opendofusdata.pet_favorites_store import load_favorites

    page = open_page(root, tmp_path)
    page._selected = HAT
    page._refresh_detail()
    page.favorite_box.select()
    page._toggle_favorite()
    assert load_favorites(page._context.config_path) == set()
    assert load_favorites(page._context.config_path, CRAFT_FAVORITES_KEY) == {HAT}


def test_craft_picks_up_recipes_downloaded_while_the_page_was_open(root, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # no data/recipes.csv fallback
    store = open_store(tmp_path)
    fill(store)
    context = make_context(tmp_path, NAMES)
    context.data_directory = tmp_path
    page = CraftPage(root, context, clock=lambda: NOW)
    page.refresh()
    assert page.table._shown == []
    write_csv_atomically(RECIPES_CSV_HEADER, recipe_rows([Recipe(HAT, ((WOOD, 2), (STONE, 1)))]),
                         tmp_path / DEFAULT_RECIPES_FILE)
    context.reference_data_changed()
    page.refresh()
    assert [row.cells[0] for row in page.table._shown] == ["Chapeau"]
    store.close()
