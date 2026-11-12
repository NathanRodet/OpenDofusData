"""Headless-safe checks of the Brisage page."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_breaking import NO_SELECTION_TEXT, BreakingPage
from opendofusdata.records import BrokenItem, LotPrice
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import NOW, make_context, open_store

CAPE, SAC = 5000, 5001
RUNES = ((1557, 3), (1522, 12), (1519, 9))
NAMES = {CAPE: "Cape Maj'Hic", SAC: "Sac-Cawotte", 1557: "Ga Pa", 1522: "Ine", 1519: "Ba"}
STAMP = "2026-11-12T09:00:00Z"


def make_page(root, tmp_path) -> BreakingPage:
    page = BreakingPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def fill(store, partial: bool = False) -> None:
    for item_id, price in ((CAPE, 20000), (1557, 11200), (1522, 100), (1519, 120)):
        if not (partial and item_id == 1522):
            store.save_lot_price(LotPrice(item_id, "Brial", 1, price, STAMP))
    store.save_record(BrokenItem("Brial", SAC, 1, 0.26, RUNES, "2026-11-12T10:00:00Z"))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.44, RUNES, "2026-11-12T11:00:00Z"))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.31, RUNES, "2026-11-12T12:00:00Z"))


def test_default_sort_puts_the_best_plus_value_first_and_unknown_last(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    plus_values = [row.cells[7] for row in page.table._shown]
    assert plus_values == ["+15 880", "+15 880", "Inconnu"]
    assert [row.cells[1] for row in page.table._shown][-1] == "Sac-Cawotte"
    assert page.table._shown[0].tag == "up"
    store.close()


def test_partial_runes_value_is_labelled(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store, partial=True)
    page = make_page(root, tmp_path)
    page.refresh()
    assert page.table._shown[0].cells[6] == "34 680 partielle"
    store.close()


def test_selecting_an_object_shows_its_coefficient_history(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(CAPE)
    assert page.name_label.cget("text") == "Cape Maj'Hic"
    assert "Brisages : 2" in page.tiles_label.cget("text")
    assert len(page.chart._points) == 2
    assert "Plus-value : +15 880" in page.runes_label.cget("text")
    store.close()


def test_empty_database_renders(root, tmp_path) -> None:
    open_store(tmp_path).close()
    page = make_page(root, tmp_path)
    page.refresh()
    assert page.table._shown == []
    assert page.name_label.cget("text") == NO_SELECTION_TEXT
