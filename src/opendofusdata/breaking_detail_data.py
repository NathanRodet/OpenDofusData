"""The detail of the Brisage page: the tabs of one broken object and of one of its breakings."""

from collections.abc import Callable, Sequence

from opendofusdata.breaking_detail_text import (
    CLASSIC_KEY, FOCUS_KEY, DetailTab, balance_tab, breaking_tab, scenario_tab,
)
from opendofusdata.breaking_items import mean_real_runes, real_totals
from opendofusdata.breaking_scenarios import Scenario, best_focus, build_scenario
from opendofusdata.breaking_texts import coefficient_text
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


def item_tabs(rows: Sequence[BreakingRow], effects: ItemEffects | None, runes: Sequence[Rune], book: PriceBook,
              name_of: Callable[[int], str]) -> list[DetailTab]:
    """The balance of every breaking, then the classic and best-focus breaking at their mean coefficient."""
    coefficient = mean_coefficient(rows)
    hdv_price = book.unit_price(rows[0].item_id, PRICE_LAST)

    def price_of(rune_id: int) -> float | None:
        return rune_price(book, rune_id)

    tabs = [balance_tab(real_totals(rows), sum(row.quantity for row in rows), price_of, hdv_price, name_of)]
    if effects is None:
        return tabs
    base = base_runes_by_action(runes)
    classic = build_scenario(effects, coefficient, base, price_of, hdv_price, mean_real_runes(rows))
    tabs.append(scenario_tab(CLASSIC_KEY, "Classique", f"Au coefficient moyen de {coefficient_text(coefficient)}",
                             classic, name_of))
    focus = best_focus(effects, coefficient, base, price_of, hdv_price)
    if focus is not None and focus.focus_rune is not None:
        tabs.append(_focus_tab(focus, classic, name_of))
    return tabs


def _focus_tab(focus: Scenario, classic: Scenario, name_of: Callable[[int], str]) -> DetailTab:
    versus = None if classic.plus_value is None or focus.plus_value is None else focus.plus_value - classic.plus_value
    return scenario_tab(FOCUS_KEY, "Focus", f"Focus le plus rentable : {name_of(focus.focus_rune)}", focus, name_of,
                        versus)


def breaking_detail(row: BreakingRow, effects: ItemEffects | None, runes: Sequence[Rune], book: PriceBook,
                    name_of: Callable[[int], str], note: str) -> DetailTab:
    """One breaking against what the classic formula expects for its coefficient (nothing when effects are unknown)."""
    scenario = None
    if effects is not None:
        real = {rune_id: count / row.quantity for rune_id, count in row.runes}
        scenario = build_scenario(effects, row.coefficient, base_runes_by_action(runes),
                                  lambda rune_id: rune_price(book, rune_id), book.unit_price(row.item_id, PRICE_LAST),
                                  real)
    return breaking_tab(row, scenario, lambda rune_id: rune_price(book, rune_id), name_of, note)
