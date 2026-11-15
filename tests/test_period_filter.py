"""The period dropdown, used the way a player does, filters the rows of a real page."""

from datetime import timedelta

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_hdv import HdvPage
from opendofusdata.records import LotPrice
from opendofusdata.time_filters import (PERIOD_ALL, PERIOD_CUSTOM, PERIOD_LAST_HOUR, PERIOD_MONTH, PERIOD_SIX_HOURS,
                                        PERIOD_TODAY, PERIOD_WEEK, PERIODS)
from opendofusdata.timeutil import format_utc
from tests.view_page_helpers import NOW, make_context, open_store

AGES = {1: timedelta(minutes=10), 2: timedelta(hours=3), 3: timedelta(days=3), 4: timedelta(days=20),
        5: timedelta(days=60)}
NAMES = {item_id: f"Objet {item_id}" for item_id in AGES}


def make_page(root, tmp_path) -> HdvPage:
    store = open_store(tmp_path)
    for item_id, age in AGES.items():
        store.save_lot_price(LotPrice(item_id, "Brial", 1, 100, format_utc(NOW - age)))
    store.close()
    return HdvPage(root, make_context(tmp_path, NAMES), clock=lambda: NOW)


def choose(page: HdvPage, period: str) -> list[str]:
    """Pick a period in the dropdown (its command is what a click runs) and return the shown names."""
    page.period_bar.menu._command(period)
    return sorted(row.cells[0] for row in page.table._shown)


def test_the_dropdown_lists_every_period_in_order(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    assert tuple(page.period_bar.menu.cget("values")) == PERIODS


@pytest.mark.parametrize("period, expected", [
    (PERIOD_LAST_HOUR, [1]), (PERIOD_SIX_HOURS, [1, 2]), (PERIOD_WEEK, [1, 2, 3]),
    (PERIOD_MONTH, [1, 2, 3, 4]), (PERIOD_ALL, [1, 2, 3, 4, 5]),
])
def test_each_relative_period_keeps_only_the_recent_rows(root, tmp_path, period, expected) -> None:
    page = make_page(root, tmp_path)
    assert choose(page, period) == [f"Objet {item_id}" for item_id in expected]


def test_today_keeps_the_rows_since_local_midnight(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    shown = choose(page, PERIOD_TODAY)
    assert "Objet 1" in shown and "Objet 5" not in shown


def test_custom_range_filters_once_valid_dates_are_applied(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    before = choose(page, PERIOD_ALL)
    page.period_bar.menu._command(PERIOD_CUSTOM)
    assert sorted(row.cells[0] for row in page.table._shown) == before  # nothing applied yet
    day = lambda moment: (NOW - moment).strftime("%d/%m/%Y")
    page.period_bar.start_entry.insert(0, day(timedelta(days=21)))
    page.period_bar.end_entry.insert(0, day(timedelta(days=19)))
    page.period_bar.apply_custom()
    assert sorted(row.cells[0] for row in page.table._shown) == ["Objet 4"]


def test_choosing_a_period_after_custom_hides_the_date_row(root, tmp_path) -> None:
    page = make_page(root, tmp_path)
    page.period_bar.menu._command(PERIOD_CUSTOM)
    assert page.period_bar._custom_row.winfo_manager() == "pack"
    page.period_bar.menu._command(PERIOD_WEEK)
    assert page.period_bar._custom_row.winfo_manager() == ""
