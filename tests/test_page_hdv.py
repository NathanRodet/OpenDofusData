"""Headless-safe checks of the HDV page over a real temporary database."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_hdv import NO_SELECTION_TEXT, HdvPage
from opendofusdata.records import LotPrice, MarketStats
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import NOW, make_context, open_store

FLECHE, SALIKRONE = 3000, 3001
NAMES = {FLECHE: "Flèche du Chafer Archer", SALIKRONE: "Salikrone"}
STAMP = "2026-11-12T18:30:00Z"
POINTS = [[1_794_470_400, 556, 40], [1_794_474_000, 557, 46]]


def make_page(root, tmp_path) -> HdvPage:
    page = HdvPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def fill(store, server: str = "Brial") -> None:
    store.save_lot_price(LotPrice(FLECHE, server, 1, 80, STAMP))
    store.save_market_stats(MarketStats(FLECHE, server, "24h", POINTS, 78, 79, 108, STAMP, STAMP, STAMP))


def shown(page: HdvPage) -> list[str]:
    return [row.cells[0] for row in page.table._shown]


def test_page_lists_items_of_the_selected_server_only(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    store.save_lot_price(LotPrice(SALIKRONE, "Kourial", 1, 500, STAMP))
    page = make_page(root, tmp_path)
    page.refresh()
    assert shown(page) == ["Flèche du Chafer Archer"]
    assert page.table._shown[0].cells[2:5] == ("80", "78", "108")
    store.close()


def test_selecting_a_row_fills_the_detail_and_the_chart(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page.table._tree.selection_set("0")
    root.update()
    assert "Flèche du Chafer Archer" in page.name_label.cget("text")
    assert len(page.chart._points) == 2
    assert ("Lot ×1", "80 kamas", None) in page.lots_list.rows
    store.close()


def test_empty_database_shows_no_rows_and_no_error(root, tmp_path) -> None:
    open_store(tmp_path).close()
    page = make_page(root, tmp_path)
    page.refresh()
    assert shown(page) == []
    assert page.name_label.cget("text") == NO_SELECTION_TEXT


def test_search_filters_rows_by_name(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    store.save_lot_price(LotPrice(SALIKRONE, "Brial", 1, 500, STAMP))
    page = make_page(root, tmp_path)
    page.refresh()
    page.search_entry.insert(0, "sali")
    page._show_rows()
    assert shown(page) == ["Salikrone"]
    store.close()


def test_missing_database_file_keeps_the_page_alive(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page.refresh()
    assert shown(page) == []
    assert "Lecture" in page.notice.cget("text")


def test_changing_the_session_server_changes_the_rows(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    store.save_lot_price(LotPrice(SALIKRONE, "Kourial", 1, 500, STAMP))
    page = make_page(root, tmp_path)
    page.refresh()
    page._context.session.apply_settings(page._context.session.database_path, "Kourial")
    page.render(page._context.session.snapshot())
    assert shown(page) == ["Salikrone"]
    store.close()


def test_the_history_of_an_item_is_a_formatted_list_not_a_text_box(root, tmp_path) -> None:
    store = open_store(tmp_path)
    fill(store)
    page = make_page(root, tmp_path)
    page.refresh()
    page.table._tree.selection_set("0")
    root.update()
    assert not hasattr(page, "history_box")
    assert page.history_list.rows and all(len(row) == 3 and row[1].startswith("Lot ×") for row in page.history_list.rows)
    store.close()
