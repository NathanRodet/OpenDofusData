"""Readable text tables of decoded values for run --verbose: pure formatting, no IO."""

from datetime import datetime

from dofus_prices.records import LotPrice, MarketStats
from dofus_prices.timeutil import STORED_TIMESTAMP_FORMAT

COLUMN_SEPARATOR = "   "
LOT_COLUMN_WIDTH = 5
PRICE_COLUMN_WIDTH = 7
PERIOD_COLUMN_WIDTH = 9
STAT_COLUMN_WIDTH = 7
CLOCK_FORMAT = "%H:%M:%S"
MINUTE_FORMAT = "%Y-%m-%d %H:%M"
PERIOD_LABELS = {"24h": "24h", "7d": "7j", "30d": "30j"}
LOT_HEADERS = ("lot", "prix")
STATS_INDENT = "  "
STATS_HEADERS = (STATS_INDENT + "période", "médiane", "moyenne", "vendus", "dernier achat (UTC)")


def group_thousands(value: int) -> str:
    """Format an integer with plain spaces as thousands separators."""
    return f"{value:,}".replace(",", " ")


def _clock_text(stored: str) -> str:
    moment = datetime.strptime(stored, STORED_TIMESTAMP_FORMAT)
    return moment.strftime(CLOCK_FORMAT) + " UTC"


def _minute_text(stored: str) -> str:
    try:
        return datetime.strptime(stored, STORED_TIMESTAMP_FORMAT).strftime(MINUTE_FORMAT)
    except ValueError:
        return stored


def _width(minimum: int, cells: list[str]) -> int:
    return max([minimum, *(len(cell) for cell in cells)])


def format_lot_prices(prices: list[LotPrice]) -> str:
    """Return the lots table of one decoded message, or "" when there is nothing."""
    if not prices:
        return ""
    sizes = [str(price.lot_size) for price in prices]
    totals = [group_thousands(price.price) for price in prices]
    size_width = _width(LOT_COLUMN_WIDTH, sizes)
    total_width = _width(PRICE_COLUMN_WIDTH, totals)
    title = f"Lots - objet {prices[0].item_id} ({_clock_text(prices[0].captured_at)})"
    lines = [f"{LOT_HEADERS[0]:>{size_width}}{COLUMN_SEPARATOR}{LOT_HEADERS[1]:>{total_width}}"]
    lines += [f"{size:>{size_width}}{COLUMN_SEPARATOR}{total:>{total_width}}"
              for size, total in zip(sizes, totals)]
    return "\n".join([title, *lines])


def _stats_columns(stats: list[MarketStats]) -> list[list[str]]:
    return [
        [STATS_INDENT + PERIOD_LABELS.get(row.period, row.period) for row in stats],
        [group_thousands(row.median) for row in stats],
        [group_thousands(row.mean) for row in stats],
        [group_thousands(row.sold_count) for row in stats],
        [_minute_text(row.last_purchase_at) for row in stats],
    ]


def _stats_line(cells: list[str], widths: list[int]) -> str:
    period, *numbers, purchase = cells
    head = f"{period:<{widths[0]}}"
    body = "".join(f"{COLUMN_SEPARATOR}{cell:>{width}}" for cell, width in zip(numbers, widths[1:]))
    return f"{head}{body}{COLUMN_SEPARATOR}{purchase}"


def format_market_stats(stats: list[MarketStats]) -> str:
    """Return the market statistics table of one decoded message, or "" when empty."""
    if not stats:
        return ""
    columns = _stats_columns(stats)
    minimums = [PERIOD_COLUMN_WIDTH, *([STAT_COLUMN_WIDTH] * 3)]
    widths = [_width(minimum, column) for minimum, column in zip(minimums, columns)]
    title = f"Cours du marché - objet {stats[0].item_id} ({_clock_text(stats[0].captured_at)})"
    rows = list(zip(*columns))
    lines = [_stats_line(list(STATS_HEADERS), widths)]
    lines += [_stats_line(list(row), widths) for row in rows]
    return "\n".join([title, *lines])
