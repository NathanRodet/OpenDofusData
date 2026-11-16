"""When a period has no data, the view shows the next period instead (and goes back if nothing is found at all)."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.page_craft import CraftPage
from opendofusdata.page_hdv import HdvPage
from opendofusdata.records import LotPrice
from opendofusdata.time_filters import (
    PERIOD_ALL, PERIOD_CUSTOM, PERIOD_LAST_HOUR, PERIOD_MONTH, PERIOD_SIX_HOURS, PERIOD_TODAY, PERIOD_WEEK,
    next_period,
)
from tests.view_page_helpers import NOW, make_context, open_store

ITEM = 3000
THREE_DAYS_AGO = "2026-11-09T10:00:00Z"
TWO_MONTHS_AGO = "2026-09-01T10:00:00Z"
FIVE_MINUTES_AGO = "2026-11-12T18:37:00Z"


@pytest.mark.parametrize("period, following", [
    (PERIOD_LAST_HOUR, PERIOD_SIX_HOURS), (PERIOD_SIX_HOURS, PERIOD_TODAY), (PERIOD_TODAY, PERIOD_WEEK),
    (PERIOD_WEEK, PERIOD_MONTH), (PERIOD_MONTH, PERIOD_ALL), (PERIOD_ALL, None), (PERIOD_CUSTOM, None),
    ("inconnu", None),
])
def test_next_period_follows_the_order_of_the_dropdown(period: str, following: str | None) -> None:
    assert next_period(period) == following


def test_the_bar_moves_to_the_next_period_and_says_when_there_is_none(root, tmp_path) -> None:
    page = HdvPage(root, make_context(tmp_path), clock=lambda: NOW)
    assert page.period_bar.selection().period == PERIOD_TODAY
    assert page.period_bar.widen() is True
    assert page.period_bar.selection().period == PERIOD_WEEK and page.period_bar.menu.get() == PERIOD_WEEK
    page.period_bar.set_period(PERIOD_ALL)
    assert page.period_bar.widen() is False
    page.period_bar.set_period(PERIOD_CUSTOM)
    assert page.period_bar.widen() is False


def hdv_with(tmp_path, root, captured_at: str) -> HdvPage:
    store = open_store(tmp_path)
    store.save_lot_price(LotPrice(ITEM, "Brial", 1, 80, captured_at))
    store.close()
    page = HdvPage(root, make_context(tmp_path, {ITEM: "Flèche"}), clock=lambda: NOW)
    page.refresh()
    return page


def test_an_empty_today_shows_the_week_and_says_so(root, tmp_path) -> None:
    page = hdv_with(tmp_path, root, THREE_DAYS_AGO)
    assert [row.cells[0] for row in page.table._shown] == ["Flèche"]
    assert page.period_bar.selection().period == PERIOD_WEEK and page.period_bar.menu.get() == PERIOD_WEEK
    notice = page.notice.cget("text")
    assert PERIOD_TODAY in notice and PERIOD_WEEK in notice


def test_it_keeps_widening_until_something_is_found(root, tmp_path) -> None:
    page = hdv_with(tmp_path, root, TWO_MONTHS_AGO)
    assert page.period_bar.selection().period == PERIOD_ALL
    assert len(page.table._shown) == 1


def test_a_period_with_data_is_left_alone(root, tmp_path) -> None:
    page = hdv_with(tmp_path, root, FIVE_MINUTES_AGO)
    assert page.period_bar.selection().period == PERIOD_TODAY
    assert page.notice.cget("text") == ""


def test_with_no_data_at_all_the_original_period_comes_back(root, tmp_path) -> None:
    page = HdvPage(root, make_context(tmp_path), clock=lambda: NOW)
    open_store(tmp_path).close()
    page.refresh()
    assert page.period_bar.selection().period == PERIOD_TODAY and page.period_bar.menu.get() == PERIOD_TODAY
    assert page.table._shown == []


def test_choosing_a_period_by_hand_clears_the_note(root, tmp_path) -> None:
    page = hdv_with(tmp_path, root, THREE_DAYS_AGO)
    assert page.notice.cget("text") != ""
    page.period_bar.set_period(PERIOD_MONTH)
    assert page.period_bar.selection().period == PERIOD_MONTH
    assert page.notice.cget("text") == ""


def test_the_craft_page_never_widens_a_period_it_does_not_show(root, tmp_path) -> None:
    page = CraftPage(root, make_context(tmp_path), clock=lambda: NOW)
    page.refresh()
    assert page.period_bar.selection().period == PERIOD_TODAY


def test_the_widened_period_notice_is_highlighted(tmp_path, root) -> None:
    from opendofusdata.ui_theme import ACCENT_COLOR

    page = hdv_with(tmp_path, root, THREE_DAYS_AGO)
    page.refresh()
    assert page.notice.cget("text_color") == ACCENT_COLOR
