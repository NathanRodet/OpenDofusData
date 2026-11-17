"""The tabs of the Brisage detail panel: this breaking, the balance of all of them, classic and focus."""

from datetime import datetime, timezone

import pytest

from opendofusdata.breaking_detail_text import (
    DetailTab, Entry, Total, balance_tab, breaking_tab, count_text, scenario_tab,
)
from opendofusdata.breaking_economy import RunesValue
from opendofusdata.breaking_scenarios import RuneLine, Scenario
from opendofusdata.breaking_view_data import BreakingRow

VIT, STR = 1523, 1525
NAMES = {VIT: "Rune Vi", STR: "Rune Fo"}
PRICES = {VIT: 100.0, STR: 1000.0}
MOMENT = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def row(runes: tuple[tuple[int, int], ...], quantity: int = 2, hdv_value: float | None = 400.0) -> BreakingRow:
    total = sum(count * PRICES[rune] for rune, count in runes)
    plus = None if hdv_value is None else total - hdv_value
    return BreakingRow(MOMENT, 5000, "Cape", quantity, 0.5, runes, None, hdv_value, RunesValue(total, False), plus)


def scenario(expected_vit: float = 4.0, expected_str: float = 0.5, hdv: float | None = 200.0) -> Scenario:
    lines = (RuneLine(VIT, expected_vit, None, 100.0), RuneLine(STR, expected_str, None, 1000.0))
    value = expected_vit * 100 + expected_str * 1000
    return Scenario(None, lines, value, None if hdv is None else value - hdv, False)


def test_small_rune_counts_keep_their_digits() -> None:
    assert [count_text(value) for value in (0.0, 0.0345, 1.0, 12.34, 250.0)] == ["0", "0.0345", "1", "12.3", "250"]


def test_one_breaking_compares_the_runes_obtained_with_the_expected_ones() -> None:
    tab = breaking_tab(row(((VIT, 10), (STR, 1))), scenario(), PRICES.get, NAMES.get, "il y a 2 j, ×2")
    assert (tab.key, tab.title, tab.headers) == ("breaking", "Ce brisage", ("Obtenu", "Attendu"))
    assert tab.note == "il y a 2 j, ×2"
    by_name = {entry.name: entry for entry in tab.entries}
    assert by_name["Rune Fo"] == Entry("Rune Fo", 1000.0, ("1", "1"), 1000.0)  # expected 0.5 per object x 2 objects
    assert by_name["Rune Vi"] == Entry("Rune Vi", 100.0, ("10", "8"), 1000.0)
    assert tab.entries[0].value >= tab.entries[1].value  # best value first


def test_one_breaking_totals_give_the_runes_the_expectation_and_the_plus_value() -> None:
    tab = breaking_tab(row(((VIT, 10), (STR, 1))), scenario(), PRICES.get, NAMES.get, "x")
    totals = {total.label: total for total in tab.totals}
    assert totals["Runes obtenues"].text == "2 000"
    assert totals["Valeur attendue"].text == "1 800"  # 900 per object x 2 objects
    assert totals["Objet (HDV)"].text == "400"
    assert totals["Plus-value"] == Total("Plus-value", "+1 600", True)


def test_a_breaking_without_a_single_rune_says_so() -> None:
    tab = breaking_tab(row(()), scenario(), PRICES.get, NAMES.get, "x")
    assert all(entry.counts[0] == "0" for entry in tab.entries)
    assert {total.label: total for total in tab.totals}["Plus-value"].positive is False


def test_without_the_effects_only_the_obtained_runes_are_listed() -> None:
    tab = breaking_tab(row(((VIT, 10),)), None, PRICES.get, NAMES.get, "x")
    assert tab.entries == (Entry("Rune Vi", 100.0, ("10", "-"), 1000.0),)
    assert "Valeur attendue" not in {total.label for total in tab.totals}


def test_an_unknown_object_price_gives_no_plus_value_line() -> None:
    tab = breaking_tab(row(((VIT, 10),), hdv_value=None), scenario(), PRICES.get, NAMES.get, "x")
    assert "Plus-value" not in {total.label for total in tab.totals}


def test_the_balance_sums_every_breaking_and_values_the_runes() -> None:
    tab = balance_tab({STR: 2, VIT: 30}, 29, PRICES.get, 10.0, NAMES.get)
    assert (tab.key, tab.title, tab.headers) == ("balance", "Bilan", ("Total", "Par objet"))
    assert tab.entries[0] == Entry("Rune Vi", 100.0, ("30", "1.03"), 3000.0)  # best value first
    assert tab.entries[1] == Entry("Rune Fo", 1000.0, ("2", "0.069"), 2000.0)
    totals = {total.label: total.text for total in tab.totals}
    assert totals == {"Objets brisés": "29", "Runes obtenues": "5 000", "Plus-value": "+4 710"}


def test_a_scenario_tab_lists_the_expected_runes_with_the_real_mean_when_known() -> None:
    lines = (RuneLine(VIT, 4.0, 3.5, 100.0), RuneLine(STR, 0.5, None, 1000.0))
    tab = scenario_tab("classic", "Classique", "Coefficient moyen 42 %", Scenario(None, lines, 900.0, 700.0, False),
                       NAMES.get)
    assert tab.headers == ("Attendu", "Réel moyen")
    assert tab.entries[0] == Entry("Rune Fo", 1000.0, ("0.5", "-"), 500.0)
    assert tab.entries[1] == Entry("Rune Vi", 100.0, ("4", "3.5"), 400.0)
    assert {total.label: total.text for total in tab.totals} == {"Runes attendues": "900", "Plus-value": "+700"}


def test_a_partial_scenario_is_flagged_and_an_unknown_plus_value_is_explained() -> None:
    lines = (RuneLine(VIT, 4.0, None, None),)
    tab = scenario_tab("classic", "Classique", "", Scenario(None, lines, 0.0, None, True), NAMES.get)
    totals = {total.label: total.text for total in tab.totals}
    assert totals["Runes attendues"] == "0 (prix de rune manquant)"
    assert totals["Plus-value"] == "inconnue (prix de l'objet inconnu)"


def test_the_focus_tab_compares_itself_with_the_classic_one() -> None:
    lines = (RuneLine(STR, 0.8, None, 1000.0),)
    tab = scenario_tab("focus", "Focus", "", Scenario(STR, lines, 800.0, 600.0, False), NAMES.get, versus=-99.0)
    assert {total.label: total.text for total in tab.totals}["Écart avec le classique"] == "-99"


def test_a_tab_is_a_plain_value_object() -> None:
    assert isinstance(DetailTab("k", "t", "n", ("a",), (), ()), DetailTab)
    with pytest.raises(AttributeError):
        DetailTab("k", "t", "n", ("a",), (), ()).key = "x"  # type: ignore[misc]


def test_the_runes_obtained_are_listed_in_a_short_text() -> None:
    from opendofusdata.breaking_texts import runes_list_text

    assert runes_list_text(((1523, 5), (1525, 3)), {1523: "Rune Do Feu", 1525: "Rune Sa"}.get) == "Do Feu ×5, Sa ×3"
    assert runes_list_text((), {}.get) == "aucune rune"
