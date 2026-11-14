"""Theoretical breaking: the formula on the real examples and the stat-line parsing."""

import pytest

from opendofusdata.breaking_theory import base_runes_by_action, breaking_weight, expected_runes
from opendofusdata.effects_csv import ItemEffects, Rune, StatLine, item_effects_of, load_item_effects, stat_line_of

RUNES = [Rune(1523, 125, 5, 0.2), Rune(1548, 125, 15, 0.2), Rune(1524, 119, 1, 1.0), Rune(7448, 174, 10, 0.1),
         Rune(1521, 124, 1, 3.0), Rune(9, 999, 1, 0.0)]


def test_weight_of_the_forum_example() -> None:
    assert breaking_weight(15, 1.0, 20) == pytest.approx(5.5)


def test_base_runes_are_the_smallest_with_a_weight() -> None:
    base = base_runes_by_action(RUNES)
    assert base[125].rune_id == 1523 and 999 not in base


def test_expected_runes_match_the_real_cape_du_piou_jaune() -> None:
    cape = ItemEffects(8233, 10, (StatLine(125, 16, 20), StatLine(119, 16, 20)))
    result = dict(expected_runes(cape, 0.347, base_runes_by_action(RUNES)))
    assert result[1523] == pytest.approx(0.555, abs=0.01)
    assert result[1524] == pytest.approx(1.39, abs=0.02)


def test_belt_example() -> None:
    belt = ItemEffects(8239, 11, (StatLine(174, 31, 50), StatLine(124, 7, 10)))
    result = dict(expected_runes(belt, 0.506, base_runes_by_action(RUNES)))
    assert result[7448] == pytest.approx(0.92, abs=0.01) and result[1521] == pytest.approx(1.0, abs=0.01)


def test_raw_item_parsing_ignores_runes_and_empty_items() -> None:
    raw = {"id": 5, "level": 10, "typeId": 6, "possibleEffects": [{"actionId": 118, "diceNum": 7, "diceSide": 10},
                                                                 {"actionId": 1, "diceNum": 0, "diceSide": 0}]}
    assert item_effects_of(raw) == ItemEffects(5, 10, (StatLine(118, 7, 10),))
    assert item_effects_of({**raw, "typeId": 78}) is None and item_effects_of({"id": 1}) is None
    assert stat_line_of({"actionId": 4, "diceNum": 1, "diceSide": 0}) == StatLine(4, 1, 1)


def test_missing_file_gives_no_effects(tmp_path) -> None:
    assert load_item_effects(tmp_path / "none.csv") == {}
