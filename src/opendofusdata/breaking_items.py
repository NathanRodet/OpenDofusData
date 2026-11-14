"""One summary per broken object, from its breakings: price, mean coefficient, mean plus-value."""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from opendofusdata.breaking_view_data import BreakingRow


@dataclass(frozen=True)
class ItemSummary:
    """What the Brisage list shows for one object."""

    item_id: int
    name: str
    hdv_price: float | None
    coefficient: float
    plus_value: float | None
    breakings: int
    last_moment: datetime


def group_by_item(rows: Sequence[BreakingRow]) -> dict[int, list[BreakingRow]]:
    """The breakings of each object, newest first."""
    grouped: dict[int, list[BreakingRow]] = defaultdict(list)
    for row in sorted(rows, key=lambda broken: broken.moment, reverse=True):
        grouped[row.item_id].append(row)
    return dict(grouped)


def mean_plus_value(rows: Sequence[BreakingRow]) -> float | None:
    """Mean plus-value per object over the breakings where it is known."""
    known = [row for row in rows if row.plus_value is not None]
    quantity = sum(row.quantity for row in known)
    return sum(row.plus_value for row in known) / quantity if quantity else None


def mean_real_runes(rows: Sequence[BreakingRow]) -> dict[int, float]:
    """Mean number of each rune really obtained per broken object."""
    totals: dict[int, int] = defaultdict(int)
    for row in rows:
        for rune_id, count in row.runes:
            totals[rune_id] += count
    objects = sum(row.quantity for row in rows)
    return {rune_id: count / objects for rune_id, count in totals.items()} if objects else {}


def item_summaries(rows: Sequence[BreakingRow], price_of: Callable[[int], float | None]) -> list[ItemSummary]:
    """One summary per broken object; the HDV price is the lowest one seen."""
    return [ItemSummary(item_id, own[0].name, price_of(item_id), sum(row.coefficient for row in own) / len(own),
                        mean_plus_value(own), len(own), own[0].moment)
            for item_id, own in group_by_item(rows).items()]
