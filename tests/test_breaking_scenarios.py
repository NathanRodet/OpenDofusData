"""Classic and focus breaking scenarios, valued on synthetic items."""

import pytest

from opendofusdata.breaking_detail_text import detail_blocks
from opendofusdata.breaking_scenarios import best_focus, build_scenario
from opendofusdata.breaking_theory import base_runes_by_action, expected_runes
from opendofusdata.effects_csv import ItemEffects, Rune, StatLine

VITALITY, STRENGTH = 125, 118
VIT_RUNE, STR_RUNE, PA_RUNE = 1523, 1525, 1557
RUNES = [Rune(VIT_RUNE, VITALITY, 5, 0.2), Rune(STR_RUNE, STRENGTH, 1, 1.0)]
BASE = base_runes_by_action(RUNES)
HAT = ItemEffects(100, 40, (StatLine(VITALITY, 40, 60), StatLine(STRENGTH, 10, 20)))
PRICES = {VIT_RUNE: 100.0, STR_RUNE: 1000.0}


def test_focus_keeps_the_target_and_halves_the_others() -> None:
    plain = dict(expected_runes(HAT, 0.5, BASE))
    focused = dict(expected_runes(HAT, 0.5, BASE, STRENGTH))
    assert focused[STR_RUNE] == pytest.approx(plain[STR_RUNE])
    assert focused[VIT_RUNE] == pytest.approx(plain[VIT_RUNE] / 2)


def test_classic_scenario_values_the_runes_and_lists_unmodelled_ones() -> None:
    scenario = build_scenario(HAT, 0.5, BASE, PRICES.get, 3000.0, {PA_RUNE: 1.0})
    expected = dict(expected_runes(HAT, 0.5, BASE))
    assert scenario.value == pytest.approx(sum(PRICES[rune] * count for rune, count in expected.items()))
    assert scenario.plus_value == pytest.approx(scenario.value - 3000.0)
    assert any(line.rune_id == PA_RUNE and line.expected == 0.0 and line.real == 1.0 for line in scenario.lines)


def test_best_focus_is_the_most_profitable_stat() -> None:
    focus = best_focus(HAT, 0.5, BASE, PRICES.get, 3000.0)
    assert focus is not None and focus.focus_rune == STR_RUNE


def test_missing_prices_are_flagged_and_unknown_hdv_price_gives_no_plus_value() -> None:
    scenario = build_scenario(HAT, 0.5, BASE, {VIT_RUNE: 100.0}.get, None, {})
    assert scenario.partial and scenario.plus_value is None


def test_detail_blocks_name_the_focus_and_compare_it_with_classic() -> None:
    classic = build_scenario(HAT, 0.5, BASE, PRICES.get, 3000.0, {})
    blocks = detail_blocks(classic, best_focus(HAT, 0.5, BASE, PRICES.get, 3000.0), {STR_RUNE: "Rune Fo"}.get)
    assert [block.title for block in blocks] == ["Brisage classique", "Focus le plus rentable : Rune Fo"]
    assert "vs classique" in blocks[1].summary
