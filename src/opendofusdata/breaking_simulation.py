"""Breaking simulation per object: what its runes are worth against the HDV price (pure logic)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from opendofusdata.breaking_view_data import BreakingRow


@dataclass(frozen=True)
class SimulationRow:
    """One object: observed coefficient and runes value, the HDV price used, and the resulting plus-value."""

    item_id: int
    name: str
    count: int
    mean_coefficient: float
    hdv_price: float | None
    overridden: bool
    mean_runes_value: float | None
    best_runes_value: float | None
    mean_plus_value: float | None
    best_plus_value: float | None
    partial: bool


def _per_object(row: BreakingRow) -> float | None:
    total = row.runes_value.total
    return None if total is None else total / row.quantity


def _listed_price(newest: BreakingRow) -> float | None:
    return None if newest.hdv_value is None else newest.hdv_value / newest.quantity


def _minus(value: float | None, price: float | None) -> float | None:
    return None if value is None or price is None else value - price


def _simulate_item(rows: Sequence[BreakingRow], overrides: Mapping[int, float]) -> SimulationRow:
    newest = max(rows, key=lambda row: row.moment)
    values = [value for value in map(_per_object, rows) if value is not None]
    price = overrides.get(newest.item_id, _listed_price(newest))
    mean_value = sum(values) / len(values) if values else None
    best_value = max(values) if values else None
    return SimulationRow(
        newest.item_id, newest.name, len(rows), sum(row.coefficient for row in rows) / len(rows), price,
        newest.item_id in overrides, mean_value, best_value, _minus(mean_value, price), _minus(best_value, price),
        any(row.runes_value.partial for row in rows))


def _plus_value_order(row: SimulationRow) -> tuple[bool, float]:
    return (row.mean_plus_value is None, -(row.mean_plus_value or 0.0))


def simulate(rows: Sequence[BreakingRow], overrides: Mapping[int, float]) -> list[SimulationRow]:
    """One row per object, best average plus-value first; a typed HDV price replaces the listed one."""
    by_item: dict[int, list[BreakingRow]] = {}
    for row in rows:
        by_item.setdefault(row.item_id, []).append(row)
    return sorted((_simulate_item(group, overrides) for group in by_item.values()), key=_plus_value_order)
