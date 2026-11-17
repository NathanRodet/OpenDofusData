"""The tabs built for one broken object and for one of its breakings, from real effects and prices."""

from datetime import datetime, timezone

import pytest

from opendofusdata.breaking_detail_data import breaking_detail, item_tabs, mean_coefficient
from opendofusdata.breaking_economy import RunesValue
from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.effects_csv import ItemEffects, Rune, StatLine
from opendofusdata.price_book import PriceBook
from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore

CAPE, VIT, STR = 5000, 1523, 1525
NAMES = {CAPE: "Cape", VIT: "Rune Vi", STR: "Rune Fo"}
EFFECTS = ItemEffects(CAPE, 40, (StatLine(125, 40, 60), StatLine(118, 10, 20)))
RUNES = [Rune(VIT, 125, 5, 0.2), Rune(STR, 118, 1, 1.0)]
MOMENT = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)


@pytest.fixture
def book() -> PriceBook:
    store = PriceStore(":memory:")
    for item_id, price in ((CAPE, 3000), (VIT, 100), (STR, 1000)):
        store.save_lot_price(LotPrice(item_id, "Brial", 1, price, "2026-11-12T09:00:00Z"))
    return PriceBook.load(store.connection, "Brial")


def row(coefficient: float, runes: tuple[tuple[int, int], ...], quantity: int = 1) -> BreakingRow:
    return BreakingRow(MOMENT, CAPE, "Cape", quantity, coefficient, runes, None, 3000.0 * quantity,
                       RunesValue(sum(count * {VIT: 100, STR: 1000}[rune] for rune, count in runes), False), None)


def test_an_object_gets_a_balance_then_classic_and_focus_tabs(book) -> None:
    rows = [row(0.4, ((VIT, 10), (STR, 2))), row(0.6, ((VIT, 20), (STR, 3)))]
    tabs = item_tabs(rows, EFFECTS, RUNES, book, NAMES.get)
    assert [tab.key for tab in tabs] == ["balance", "classic", "focus"]
    assert tabs[1].note == "Au coefficient moyen de 50 %" and tabs[2].note.startswith("Focus le plus rentable : ")
    assert any(total.label == "Écart avec le classique" for total in tabs[2].totals)


def test_without_the_effects_only_the_balance_is_given(book) -> None:
    tabs = item_tabs([row(0.4, ((VIT, 10),))], None, RUNES, book, NAMES.get)
    assert [tab.key for tab in tabs] == ["balance"]


def test_one_breaking_is_compared_with_the_expectation_at_its_own_coefficient(book) -> None:
    tab = breaking_detail(row(0.5, ((VIT, 10), (STR, 2)), quantity=2), EFFECTS, RUNES, book, NAMES.get, "il y a 2 j")
    assert tab.key == "breaking" and tab.note == "il y a 2 j"
    assert {total.label for total in tab.totals} >= {"Runes obtenues", "Valeur attendue", "Objet (HDV)"}
    assert all(entry.counts[1] != "-" for entry in tab.entries)


def test_one_breaking_without_effects_lists_what_was_obtained(book) -> None:
    tab = breaking_detail(row(0.5, ((VIT, 10),)), None, RUNES, book, NAMES.get, "x")
    assert [entry.name for entry in tab.entries] == ["Rune Vi"] and tab.entries[0].counts == ("10", "-")


def test_the_mean_coefficient_averages_the_breakings() -> None:
    assert mean_coefficient([row(0.4, ()), row(0.6, ())]) == pytest.approx(0.5)
