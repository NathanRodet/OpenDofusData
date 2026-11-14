"""Which unit price the player wants for estimates: pure logic."""

from collections.abc import Mapping
from dataclasses import dataclass

PRICE_LAST = "last"
PRICE_MEDIAN = "median"
PRICE_MEAN = "mean"
PRICE_MODES = (PRICE_LAST, PRICE_MEDIAN, PRICE_MEAN)
PRICE_MODE_LABELS = {PRICE_LAST: "Dernier prix HDV", PRICE_MEDIAN: "Médian 24 h", PRICE_MEAN: "Moyen 24 h"}
SINGLE_UNIT_LOT = 1
BULK_LOT_SIZES = (100, 1000)


@dataclass(frozen=True)
class ItemPrices:
    """What is known of an item: its latest price per lot size and its 24 h statistics."""

    lots: Mapping[int, int]
    median_24h: int | None
    mean_24h: int | None
    seen_at: str | None = None  # stored UTC time of the newest lot price


def _last_unit_price(lots: Mapping[int, int]) -> float | None:
    if SINGLE_UNIT_LOT in lots:
        return float(lots[SINGLE_UNIT_LOT])
    if not lots:
        return None
    smallest = min(lots)
    return lots[smallest] / smallest


def _optional_float(value: int | None) -> float | None:
    return None if value is None else float(value)


def unit_price(prices: ItemPrices | None, mode: str) -> float | None:
    """The price of one unit under the chosen mode; None when it is unknown (0 is a real price)."""
    if prices is None:
        return None
    if mode == PRICE_MEDIAN:
        return _optional_float(prices.median_24h)
    if mode == PRICE_MEAN:
        return _optional_float(prices.mean_24h)
    return _last_unit_price(prices.lots)


def best_lot_unit_price(prices: ItemPrices | None) -> float | None:
    """The cheapest price per unit over every known lot size (a x100 lot is often cheaper per unit)."""
    if prices is None or not prices.lots:
        return None
    return min(price / size for size, price in prices.lots.items())


def bulk_unit_price(prices: ItemPrices | None) -> float | None:
    """The cheapest price per unit among the x100 and x1000 lots (what pet feeding buys); None when neither is known."""
    if prices is None:
        return None
    known = [prices.lots[size] / size for size in BULK_LOT_SIZES if size in prices.lots]
    return min(known) if known else None
