"""Headless-safe checks of the Brisage page and its two tabs."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_breaking import TAB_PURCHASES, TAB_SIMULATION, BreakingPage
from opendofusdata.page_breaking_buys import PurchasesPage
from opendofusdata.page_breaking_sim import SimulationPage
from opendofusdata.records import BrokenItem, LotPrice
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import NOW, make_context, open_store

CAPE, SAC = 5000, 5001
RUNES = ((1557, 3), (1522, 12), (1519, 9))
NAMES = {CAPE: "Cape Maj'Hic", SAC: "Sac-Cawotte", 1557: "Ga Pa", 1522: "Ine", 1519: "Ba"}
STAMP = "2026-11-12T09:00:00Z"
FIRST_CAPE = f"{CAPE}|2026-11-12T11:00:00Z"


def fill(store, partial: bool = False) -> None:
    for item_id, price in ((CAPE, 20000), (1557, 11200), (1522, 100), (1519, 120)):
        if not (partial and item_id == 1522):
            store.save_lot_price(LotPrice(item_id, "Brial", 1, price, STAMP))
    store.save_record(BrokenItem("Brial", SAC, 1, 0.26, RUNES, "2026-11-12T10:00:00Z"))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.44, RUNES, "2026-11-12T11:00:00Z"))
    store.save_record(BrokenItem("Brial", CAPE, 1, 0.31, RUNES, "2026-11-12T12:00:00Z"))


def make_sim(root, tmp_path) -> SimulationPage:
    page = SimulationPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def make_buys(root, tmp_path) -> PurchasesPage:
    page = PurchasesPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def cells(page, name: str) -> tuple[str, ...]:
    return next(row.cells for row in page.table._shown if row.cells[page._name_column] == name)


def test_the_page_has_two_tabs_and_only_the_visible_one_renders(root, tmp_path) -> None:
    page = BreakingPage(root, make_context(tmp_path, NAMES))
    assert page.current_tab == TAB_SIMULATION
    page.show_tab(TAB_PURCHASES)
    assert page.purchases.frame.winfo_manager() == "pack" and page.simulation.frame.winfo_manager() == ""


def test_simulation_lists_one_row_per_object_with_the_potential(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_sim(root, tmp_path)
    page.refresh()
    assert [row.cells[0] for row in page.table._shown] == ["Cape Maj'Hic", "Sac-Cawotte"]
    cape = cells(page, "Cape Maj'Hic")
    assert (cape[1], cape[2], cape[3], cape[4], cape[6]) == ("20 000", "38 %", "2", "35 880", "+15 880")
    assert cells(page, "Sac-Cawotte")[1] == "Inconnu"
    store.close()


def test_typing_an_hdv_price_changes_the_simulation_and_is_kept(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_sim(root, tmp_path)
    page.refresh()
    page.price_typed(CAPE, 1, "30 000")
    cape = cells(page, "Cape Maj'Hic")
    assert (cape[1], cape[6]) == ("30 000 (modifié)", "+5 880")
    page.price_typed(SAC, 1, "1k")
    assert cells(page, "Sac-Cawotte")[6] == "+34 880"
    page.price_typed(CAPE, 1, "")
    assert cells(page, "Cape Maj'Hic")[1] == "20 000"
    store.close()


def test_a_bad_typed_price_is_refused(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_sim(root, tmp_path)
    page.refresh()
    page.price_typed(CAPE, 1, "beaucoup")
    assert "illisible" in page.notice.cget("text")
    assert cells(page, "Cape Maj'Hic")[1] == "20 000"
    store.close()


def test_partial_runes_do_not_break_the_simulation(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store, partial=True)
    page = make_sim(root, tmp_path)
    page.refresh()
    assert cells(page, "Cape Maj'Hic")[4] == "34 680"
    store.close()


def test_purchases_default_to_the_hdv_price_of_the_moment_and_show_the_gain(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_buys(root, tmp_path)
    page.refresh()
    first = next(row for row in page.table._shown if row.key == FIRST_CAPE)
    assert (first.cells[4], first.cells[5], first.cells[6]) == ("20 000", "35 880", "+15 880")
    assert "Gain total" in page.totals_label.cget("text")
    store.close()


def test_a_typed_purchase_price_sets_the_gain_and_the_totals(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_buys(root, tmp_path)
    page.refresh()
    page.price_typed(FIRST_CAPE, 4, "40000")
    first = next(row for row in page.table._shown if row.key == FIRST_CAPE)
    assert (first.cells[4], first.cells[6]) == ("40 000 (modifié)", "-4 120")
    assert "Dépensé : 60 000" in page.totals_label.cget("text")
    page._selection_changed(FIRST_CAPE)
    assert "Ga Pa ×3" in page.runes_label.cget("text")
    store.close()


def test_empty_database_renders_on_both_tabs(root, tmp_path) -> None:
    open_store(tmp_path).close()
    for make in (make_sim, make_buys):
        page = make(root, tmp_path)
        page.refresh()
        assert page.table._shown == []
