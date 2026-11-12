"""Headless-safe checks of the Logs page and its filters."""

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.log_feed import MAX_LOG_LINES, LogEntry
from opendofusdata.log_filters import KIND_ALL, filter_entries
from opendofusdata.page_logs import LogsPage
from opendofusdata.records import BrokenItem, LotPrice
from opendofusdata.time_filters import PERIOD_ALL
from tests.view_page_helpers import make_context

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)
NAMES = {307: "Ailes de Moskito", 308: "Cape Maj'Hic"}


def name_of(item_id: int) -> str:
    return NAMES.get(item_id, f"Objet {item_id}")


def lot(item_id: int) -> LotPrice:
    return LotPrice(item_id, "Brial", 10, 5868, "2026-11-11T13:32:05Z")


def make_page(root, tmp_path) -> LogsPage:
    page = LogsPage(root, make_context(tmp_path, NAMES), clock=lambda: MOMENT)
    page.period_bar.set_period(PERIOD_ALL)
    return page


def test_filter_by_kind_text_and_window() -> None:
    entries = [LogEntry(MOMENT - timedelta(hours=5), "HDV", 307, "lot ×10", "5 868"),
               LogEntry(MOMENT, "Brisage", 308, "44 %", "3 runes"),
               LogEntry(MOMENT, "HDV", 308, "lot ×1", "20 000")]
    everything = (None, None)
    assert len(filter_entries(entries, "", KIND_ALL, everything, name_of)) == 3
    assert [entry.category for entry in filter_entries(entries, "", "Brisage", everything, name_of)] == ["Brisage"]
    assert len(filter_entries(entries, "CAPE", KIND_ALL, everything, name_of)) == 2
    assert len(filter_entries(entries, "", KIND_ALL, (MOMENT - timedelta(hours=1), None), name_of)) == 2


def test_the_feed_records_without_any_switch_and_the_page_shows_it(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page._context.session.feed.add(lot(307), MOMENT)
    page.render(None)
    assert [row.cells[2:] for row in page.table._shown] == [("Ailes de Moskito", "lot ×10", "5 868")]


def test_clear_empties_the_feed_but_not_the_database(root, tmp_path) -> None:
    from opendofusdata.storage import PriceStore

    store = PriceStore(str(tmp_path / "p.db"))
    store.save_lot_price(lot(307))
    page = make_page(root, tmp_path)
    page._context.session.feed.add(lot(307), MOMENT)
    page.render(None)
    page.clear()
    assert page.table._shown == []
    assert len(store.latest_prices()) == 1
    store.close()


def test_notes_for_unknown_pets_still_appear(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page._context.session.feed.add_note("Familier", "ressource inconnue #5", MOMENT, "ignorée", "reconnecte")
    page.render(None)
    assert page.table._shown[0].cells[1:3] == ("Familier", "ressource inconnue #5")


def test_the_table_shows_at_most_the_feed_capacity(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    for item_id in range(MAX_LOG_LINES + 50):
        page._context.session.feed.add(lot(item_id), MOMENT)
    page.render(None)
    assert len(page.table._shown) == MAX_LOG_LINES


def test_the_logs_follow_a_changed_name_lookup(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page._context.session.feed.add(lot(307), MOMENT)
    page.render(None)
    page._context.name_of = lambda item_id: "Nouveau nom"
    page.render(None)
    assert page.table._shown[0].cells[2] == "Nouveau nom"


def test_broken_items_show_their_runes() -> None:
    from opendofusdata.log_feed import entry_from_record

    entry = entry_from_record(BrokenItem("Brial", 308, 1, 0.44, ((1557, 3),), "t"), MOMENT)
    assert (entry.category, entry.detail, entry.value) == ("Brisage", "44 %", "3 runes")
