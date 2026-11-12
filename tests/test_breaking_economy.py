"""Tests of the breaking value rules (Cape Maj'Hic example)."""

from opendofusdata.breaking_economy import RunesValue, object_value, plus_value, runes_value

RUNES = ((1557, 3), (1522, 12), (1519, 9))
PRICES = {1557: 11200.0, 1522: 100.0, 1519: 120.0}


def test_runes_value_adds_quantity_times_price() -> None:
    assert runes_value(RUNES, PRICES.get) == RunesValue(35880.0, False)


def test_an_unknown_rune_counts_zero_and_marks_the_value_partial() -> None:
    prices = {1557: 11200.0, 1519: 120.0}
    assert runes_value(RUNES, prices.get) == RunesValue(34680.0, True)


def test_no_known_price_gives_an_unknown_total() -> None:
    assert runes_value(RUNES, {}.get) == RunesValue(None, False)


def test_plus_value() -> None:
    assert plus_value(RunesValue(35880.0, False), 20000.0) == 15880.0
    assert plus_value(RunesValue(None, False), 20000.0) is None
    assert plus_value(RunesValue(35880.0, False), None) is None


def test_object_value() -> None:
    assert object_value(900.0, 2) == 1800.0
    assert object_value(None, 2) is None
