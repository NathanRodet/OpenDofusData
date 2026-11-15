"""The detail of one broken object: its classic breaking and its best focus, valued with the rune prices."""

from collections.abc import Callable, Mapping, Sequence

from opendofusdata.breaking_detail_text import DetailBlock, detail_blocks, real_block
from opendofusdata.breaking_items import mean_real_runes, real_totals
from opendofusdata.breaking_scenarios import best_focus, build_scenario
from opendofusdata.breaking_theory import base_runes_by_action
from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.effects_csv import ItemEffects, Rune
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST, PRICE_MEAN


def rune_price(book: PriceBook, rune_id: int) -> float | None:
    """The average rune price, else the cheapest listing."""
    price = book.unit_price(rune_id, PRICE_MEAN)
    return price if price is not None else book.unit_price(rune_id, PRICE_LAST)


def mean_coefficient(rows: Sequence[BreakingRow]) -> float:
    """The mean coefficient of the breakings of one object."""
    return sum(row.coefficient for row in rows) / len(rows)


def item_blocks(rows: Sequence[BreakingRow], effects: ItemEffects, runes: Sequence[Rune], book: PriceBook,
                name_of: Callable[[int], str]) -> list[DetailBlock]:
    """Classic and best-focus blocks of the object, at the mean coefficient of its breakings."""
    base: Mapping[int, Rune] = base_runes_by_action(runes)
    coefficient = mean_coefficient(rows)
    hdv_price = book.unit_price(rows[0].item_id, PRICE_LAST)

    def price_of(rune_id: int) -> float | None:
        return rune_price(book, rune_id)

    classic = build_scenario(effects, coefficient, base, price_of, hdv_price, mean_real_runes(rows))
    real = real_block(real_totals(rows), sum(row.quantity for row in rows), price_of, hdv_price, name_of)
    return [real, *detail_blocks(classic, best_focus(effects, coefficient, base, price_of, hdv_price), name_of)]
