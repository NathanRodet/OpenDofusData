"""Headless-safe checks of the Brisage page on synthetic data."""

import customtkinter
import pytest

pytest.importorskip("customtkinter")

from opendofusdata.effects_csv import (EFFECTS_CSV_HEADER, EFFECTS_FILE, RUNES_CSV_HEADER, RUNES_FILE,
                                       ItemEffects, Rune, StatLine, effects_rows, runes_rows)
from opendofusdata.names_build import write_csv_atomically
from opendofusdata.page_breaking import BreakingPage
from opendofusdata.records import BrokenItem, LotPrice
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import NOW, make_context, open_store

CAPE, SAC, VIT_RUNE, STR_RUNE = 5000, 5001, 1523, 1525
NAMES = {CAPE: "Cape", SAC: "Sac", VIT_RUNE: "Rune Vi", STR_RUNE: "Rune Fo"}
STAMP = "2026-11-12T09:00:00Z"


def make_page(root, tmp_path, with_effects: bool = True) -> BreakingPage:
    context = make_context(tmp_path, NAMES)
    context.data_directory = tmp_path
    if with_effects:
        item = ItemEffects(CAPE, 40, (StatLine(125, 40, 60), StatLine(118, 10, 20)))
        write_csv_atomically(EFFECTS_CSV_HEADER, effects_rows([item]), tmp_path / EFFECTS_FILE)
        write_csv_atomically(RUNES_CSV_HEADER, runes_rows([Rune(VIT_RUNE, 125, 5, 0.2), Rune(STR_RUNE, 118, 1, 1.0)]),
                             tmp_path / RUNES_FILE)
    page = BreakingPage(root, context, clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def fill(store) -> None:
    for item_id, price in ((CAPE, 3000), (VIT_RUNE, 100), (STR_RUNE, 1000)):
        store.save_lot_price(LotPrice(item_id, "Brial", 1, price, STAMP))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.4, ((VIT_RUNE, 10), (STR_RUNE, 2)), "2026-11-12T11:00:00Z"))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.6, ((VIT_RUNE, 20), (STR_RUNE, 3)), "2026-11-12T12:00:00Z"))
    store.save_record(BrokenItem("Brial", SAC, 1, 0.3, ((VIT_RUNE, 1),), "2026-11-12T10:00:00Z"))


def test_the_list_has_one_row_per_object_with_price_coefficient_and_mean_plus_value(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    cells = {row.cells[0]: row.cells for row in page.table._shown}
    assert cells["Cape"] == ("Cape", "3 000", "50 %", "+1 000", "2")
    assert set(cells) == {"Cape", "Sac"}
    store.close()


def test_selecting_an_object_lists_its_breakings_and_offers_the_balance_classic_and_focus(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    assert len(page.breakings_table._shown) == 2
    assert page.panel.tab_keys == ["balance", "classic", "focus"] and page.panel.current_key == "balance"
    assert "Cape" in page.breakings_title.cget("text") and "(2)" in page.breakings_title.cget("text")
    store.close()


def test_a_breaking_row_shows_the_runes_obtained(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    cells = [row.cells for row in page.breakings_table._shown]
    assert {cell[3] for cell in cells} == {"Vi ×20, Fo ×3", "Vi ×10, Fo ×2"}
    by_coefficient = {cell[2]: cell for cell in cells}
    assert by_coefficient["60 %"][1] == "1" and by_coefficient["60 %"][3] == "Vi ×20, Fo ×3"
    store.close()


def test_clicking_a_breaking_opens_its_own_tab_first(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    key = page.breakings_table._shown[0].key
    page.breakings_table._tree.selection_set(str(page.breakings_table._shown.index(page.breakings_table._shown[0])))
    root.update()
    assert page._chosen_breaking == key
    assert page.panel.tab_keys[0] == "breaking" and page.panel.current_key == "breaking"
    shown = [label.cget("text") for label in _labels(page.panel.rune_grid)]
    assert "Obtenu" in shown and "Attendu" in shown
    store.close()


def test_the_chosen_tab_and_breaking_survive_the_periodic_refresh(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    page.breakings_table._tree.selection_set("0")
    root.update()
    page.panel._title_chosen("Bilan")
    page.refresh()
    assert page.panel.current_key == "balance" and page._chosen_breaking is not None
    store.close()


def test_changing_object_forgets_the_chosen_breaking(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    page.breakings_table._tree.selection_set("0")
    root.update()
    page._selection_changed(SAC)
    assert page._chosen_breaking is None and "breaking" not in page.panel.tab_keys


def test_clearing_the_selection_shows_the_invitation(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    page._selection_changed(None)
    assert page.panel.tab_keys == [] and "Sélectionne un objet" in page.panel.name_label.cget("text")
    assert page.breakings_table._shown == []
    store.close()


def _labels(widget) -> list[customtkinter.CTkLabel]:
    found = []
    for child in widget.winfo_children():
        if isinstance(child, customtkinter.CTkLabel):
            found.append(child)
        found.extend(_labels(child))
    return found


def test_missing_effects_are_explained(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path, with_effects=False)
    page.refresh()
    page._selection_changed(SAC)
    assert "Télécharger les données de référence" in page.panel.hint_label.cget("text")
    store.close()


def test_breaking_picks_up_effects_downloaded_while_the_page_was_open(root, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # no data/ fallback
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path, with_effects=False)
    page.refresh()
    page._selection_changed(CAPE)
    assert not page._effects
    item = ItemEffects(CAPE, 40, (StatLine(125, 40, 60),))
    write_csv_atomically(EFFECTS_CSV_HEADER, effects_rows([item]), tmp_path / EFFECTS_FILE)
    page._context.reference_data_changed()
    page.refresh()
    assert CAPE in page._effects
    store.close()
