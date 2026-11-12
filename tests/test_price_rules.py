"""Tests of the unit price rules."""

from opendofusdata.price_rules import PRICE_LAST, PRICE_MEAN, PRICE_MEDIAN, PRICE_MODE_LABELS, ItemPrices, unit_price


def test_last_price_uses_lot_one() -> None:
    assert unit_price(ItemPrices({1: 557, 10: 5410}, None, None), PRICE_LAST) == 557.0


def test_last_price_without_lot_one_divides_the_smallest_lot() -> None:
    assert unit_price(ItemPrices({10: 5410, 100: 52300}, None, None), PRICE_LAST) == 541.0


def test_median_and_mean_modes() -> None:
    prices = ItemPrices({1: 557}, 520, 530)
    assert unit_price(prices, PRICE_MEDIAN) == 520.0
    assert unit_price(prices, PRICE_MEAN) == 530.0


def test_price_zero_is_a_price() -> None:
    assert unit_price(ItemPrices({1: 0}, 0, 0), PRICE_LAST) == 0.0
    assert unit_price(ItemPrices({}, 0, None), PRICE_MEDIAN) == 0.0


def test_unknown_when_nothing_is_known() -> None:
    assert unit_price(None, PRICE_LAST) is None
    assert unit_price(ItemPrices({}, None, None), PRICE_LAST) is None


def test_median_mode_without_stats_is_unknown() -> None:
    assert unit_price(ItemPrices({1: 557}, None, None), PRICE_MEDIAN) is None


def test_every_mode_has_a_label() -> None:
    assert PRICE_MODE_LABELS[PRICE_LAST] == "Dernier prix HDV"
