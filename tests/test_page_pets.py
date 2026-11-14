"""Headless-safe checks of the Familiers page."""

import json

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_pets import PetsPage
from opendofusdata.records import LotPrice, MarketStats, PetFeeding, PetState
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import NOW, make_context, open_store

BOUE, PATTE, GRAIN, NOMOON = 1001, 1002, 1003, 9000
NAMES = {BOUE: "Boue du Boo", PATTE: "Patte de Gruche", GRAIN: "Graine", NOMOON: "Nomoon"}
STAMP = "2026-11-12T09:00:00Z"


def feeding(item_id: int, units: int, before: int, after: int, stamp: str = "2026-11-12T10:00:00Z") -> PetFeeding:
    return PetFeeding("Brial", NOMOON, ((item_id, units),), PetState(35, before, 9999, 0),
                      PetState(35, after, 9999, 0), stamp)


def make_page(root, tmp_path) -> PetsPage:
    page = PetsPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def fill(store) -> None:
    store.save_lot_price(LotPrice(PATTE, "Brial", 1, 240, STAMP))
    store.save_record(feeding(BOUE, 9, 100, 101))
    store.save_record(feeding(PATTE, 1, 101, 103))


def by_name(page: PetsPage) -> dict[str, tuple[str, ...]]:
    return {row.cells[0]: row.cells for row in page.table._shown}


def test_rows_are_sorted_by_kamas_per_xp_with_unknown_last(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    assert [row.cells[0] for row in page.table._shown] == ["Patte de Gruche", "Boue du Boo"]
    store.close()


def test_texts_follow_the_display_rules(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    patte, boue = by_name(page)["Patte de Gruche"], by_name(page)["Boue du Boo"]
    assert (patte[2], patte[4], patte[5], patte[7]) == ("240", "+2", "120", "21 550 920")
    assert (boue[2], boue[4], boue[5], boue[7]) == ("Inconnu", "1 XP pour 9", "Inconnu", "Inconnu")
    store.close()


def test_unreliable_row_is_marked(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    store.save_record(feeding(GRAIN, 1, 0, 12))
    page = make_page(root, tmp_path)
    page.refresh()
    assert by_name(page)["Patte de Gruche"][6] == "1 peu fiable"
    assert by_name(page)["Graine"][6] == "1"
    store.close()


def test_without_a_recent_bulk_price_the_average_price_is_used_whatever_the_price_mode(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    store.save_market_stats(MarketStats(PATTE, "Brial", "24h", [], 200, 210, 5, STAMP, STAMP, STAMP))
    page = make_page(root, tmp_path)
    page.refresh()
    assert by_name(page)["Patte de Gruche"][5] == "105" and by_name(page)["Patte de Gruche"][3] == "210"
    (tmp_path / "config.json").write_text(json.dumps({"price_mode": "median"}), encoding="utf-8")
    page.refresh()
    assert by_name(page)["Patte de Gruche"][5] == "105"
    store.close()


def test_selecting_a_resource_lists_its_upgrades(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page._selection_changed(PATTE)
    assert "Nomoon" in page.upgrades_label.cget("text") and "+2 XP" in page.upgrades_label.cget("text")
    store.close()


def test_empty_database_renders(root, tmp_path) -> None:
    open_store(tmp_path).close()
    page = make_page(root, tmp_path)
    page.refresh()
    assert page.table._shown == []


def test_the_form_suggests_items_while_typing_and_adds_the_typed_experience(root, tmp_path) -> None:
    from opendofusdata.pet_manual_store import load_manual

    store = open_store(tmp_path)
    store.connection.executemany("INSERT INTO items (item_id, name_fr, type_fr) VALUES (?, ?, ?)",
                                 [(BOUE, "Boue du Boo", "Ressource"), (GRAIN, "Boue grise", "Ressource")])
    store.connection.commit()
    page = make_page(root, tmp_path)
    page.form.item_box.insert(0, "boue")
    page.form.update_choices()
    assert [button.cget("text") for button in page.form.suggestions.winfo_children()] == ["Boue du Boo", "Boue grise"]
    page.form.choose("Boue du Boo")
    page.form.units_entry.insert(0, "10")
    page.form.experience_entry.insert(0, "50")
    page.form.add()
    assert load_manual(page._context.config_path)[BOUE].experience == 50 and not page.form.suggestions.winfo_children()
    store.close()


def test_the_search_field_is_not_refilled_while_the_same_row_stays_selected(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page._selection_changed(BOUE)
    page.form.item_box.delete(0, "end")
    page.form.item_box.insert(0, "gra")
    page._selection_changed(BOUE)
    assert page.form.item_box.get() == "gra"
    page._selection_changed(PATTE)
    assert page.form.item_box.get() == "Patte de Gruche"
