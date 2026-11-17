"""Display texts of the Brisage page."""

from collections.abc import Callable, Sequence

from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.ui_table import TAG_DOWN, TAG_UP
from opendofusdata.value_format import UNKNOWN_TEXT, format_kamas

PERCENT = 100
PARTIAL_SUFFIX = " partielle"
RUNE_PREFIX = "Rune "
NO_RUNE_TEXT = "aucune rune"
RUNE_SEPARATOR = ", "


def coefficient_text(coefficient: float) -> str:
    """A coefficient (0.44) as a percentage text (44 %)."""
    return f"{round(coefficient * PERCENT)} %"


def runes_text(row: BreakingRow) -> str:
    """The runes value, marked partial when a rune price is missing."""
    if row.runes_value.total is None:
        return UNKNOWN_TEXT
    return format_kamas(row.runes_value.total) + (PARTIAL_SUFFIX if row.runes_value.partial else "")


def runes_list_text(runes: Sequence[tuple[int, int]], name_of: Callable[[int], str]) -> str:
    """The runes obtained as 'Do Feu ×5, Sa ×3' (the 'Rune ' prefix is dropped), or that there was none."""
    if not runes:
        return NO_RUNE_TEXT
    return RUNE_SEPARATOR.join(f"{name_of(rune_id).removeprefix(RUNE_PREFIX)} ×{count}" for rune_id, count in runes)


def plus_value_tag(plus_value: float | None) -> str | None:
    """The colour tag of a plus-value row."""
    if plus_value is None:
        return None
    return TAG_UP if round(plus_value) >= 0 else TAG_DOWN
