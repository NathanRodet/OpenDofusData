"""Tests of the breaking simulation and of the typed prices."""

from datetime import datetime, timezone

import pytest

from opendofusdata.breaking_economy import RunesValue
from opendofusdata.breaking_simulation import simulate
from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.user_prices import (
    HDV_OVERRIDES_KEY, load_prices, parse_kamas, store_price,
)


def breaking(item_id: int, hour: int, coefficient: float, runes: float | None, hdv: float | None,
             quantity: int = 1, partial: bool = False) -> BreakingRow:
    value = RunesValue(runes, partial)
    plus = None if runes is None or hdv is None else runes - hdv
    return BreakingRow(datetime(2026, 11, 12, hour, tzinfo=timezone.utc), item_id, f"Objet {item_id}", quantity,
                       coefficient, (), None, hdv, value, plus)


def test_means_best_and_plus_value_against_the_listed_price() -> None:
    rows = [breaking(1, 8, 0.40, 30000.0, 20000.0), breaking(1, 9, 0.50, 50000.0, 20000.0)]
    (row,) = simulate(rows, {})
    assert (row.count, row.hdv_price, row.overridden) == (2, 20000.0, False)
    assert row.mean_coefficient == pytest.approx(0.45)
    assert (row.mean_runes_value, row.best_runes_value) == (40000.0, 50000.0)
    assert (row.mean_plus_value, row.best_plus_value) == (20000.0, 30000.0)


def test_a_typed_price_replaces_the_listed_one() -> None:
    (row,) = simulate([breaking(1, 8, 0.4, 30000.0, 20000.0)], {1: 35000.0})
    assert (row.hdv_price, row.overridden, row.mean_plus_value) == (35000.0, True, -5000.0)


def test_values_are_per_object_for_a_stack() -> None:
    (row,) = simulate([breaking(1, 8, 0.4, 60000.0, 40000.0, quantity=2)], {})
    assert (row.hdv_price, row.mean_runes_value, row.mean_plus_value) == (20000.0, 30000.0, 10000.0)


def test_unknown_price_sorts_last_and_a_typed_price_fills_it() -> None:
    rows = [breaking(1, 8, 0.4, 30000.0, None), breaking(2, 8, 0.4, 30000.0, 20000.0)]
    assert [row.item_id for row in simulate(rows, {})] == [2, 1]
    assert simulate(rows, {1: 1000.0})[0].item_id == 1


def test_parse_kamas() -> None:
    assert parse_kamas("95000") == 95000.0 and parse_kamas("95 000") == 95000.0
    assert parse_kamas("1,5k") == 1500.0 and parse_kamas("2m") == 2_000_000.0
    assert parse_kamas("  ") is None
    for bad in ("abc", "-5"):
        with pytest.raises(ValueError):
            parse_kamas(bad)


def test_prices_are_saved_loaded_and_removed(tmp_path) -> None:
    path = tmp_path / "config.json"
    assert store_price(path, HDV_OVERRIDES_KEY, "8216", 95000.0)
    assert load_prices(path, HDV_OVERRIDES_KEY) == {"8216": 95000.0}
    assert store_price(path, HDV_OVERRIDES_KEY, "8216", None)
    assert load_prices(path, HDV_OVERRIDES_KEY) == {}
