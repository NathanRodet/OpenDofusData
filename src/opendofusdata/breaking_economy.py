"""Value of broken runes and plus-value against the object's price: pure logic."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RunesValue:
    """The estimated value of the runes; `partial` when some rune had no known price."""

    total: float | None
    partial: bool


def runes_value(runes: Sequence[tuple[int, int]], price_of: Callable[[int], float | None]) -> RunesValue:
    """Add quantity × unit price of each rune; unknown runes count 0 and make the value partial."""
    total, known, unknown = 0.0, 0, 0
    for rune_id, quantity in runes:
        price = price_of(rune_id)
        if price is None:
            unknown += 1
            continue
        known += 1
        total += quantity * price
    if not runes:
        return RunesValue(0.0, False)  # an object that gave no rune is worth nothing, not unknown
    return RunesValue(total if known else None, unknown > 0 and known > 0)


def object_value(unit_price: float | None, quantity: int) -> float | None:
    """The price of the broken objects, None when the object price is unknown."""
    return None if unit_price is None else unit_price * quantity


def plus_value(runes: RunesValue, object_hdv_value: float | None) -> float | None:
    """Runes value minus the object's HDV value; None when either is unknown."""
    if runes.total is None or object_hdv_value is None:
        return None
    return runes.total - object_hdv_value
