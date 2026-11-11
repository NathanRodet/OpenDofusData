"""Plain data records stored by the price database: pure data."""

from dataclasses import dataclass

LOT_SIZES = (1, 10, 100, 1000)
MARKET_PERIODS = ("24h", "7d", "30d")


@dataclass
class LotPrice:
    """Total price of one lot of an item on a server (never a unit price)."""

    item_id: int
    server: str
    lot_size: int
    price: int
    captured_at: str


@dataclass(frozen=True)
class RecyclingEvent:
    """One recycling: what was in the window (item id, quantity) and the nuggets obtained."""

    server: str
    items: tuple[tuple[int, int], ...]
    nuggets: int
    captured_at: str


@dataclass
class MarketStats:
    """Market statistics of an item over a period, with its price curve."""

    item_id: int
    server: str
    period: str
    points: list[tuple[int, int, int]]  # (unix seconds, price, quantity)
    median: int
    mean: int
    sold_count: int
    server_updated_at: str
    last_purchase_at: str
    captured_at: str

Record = LotPrice | MarketStats | RecyclingEvent
