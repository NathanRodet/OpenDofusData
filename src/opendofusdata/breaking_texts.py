"""Display texts shared by the two Brisage tabs."""

from opendofusdata.breaking_view_data import BreakingRow
from opendofusdata.ui_table import TAG_DOWN, TAG_UP
from opendofusdata.value_format import UNKNOWN_TEXT, format_kamas

PERCENT = 100
PARTIAL_SUFFIX = " partielle"
MODIFIED_SUFFIX = " (modifié)"


def coefficient_text(coefficient: float) -> str:
    """A coefficient (0.44) as a percentage text (44 %)."""
    return f"{round(coefficient * PERCENT)} %"


def runes_text(row: BreakingRow) -> str:
    """The runes value, marked partial when a rune price is missing."""
    if row.runes_value.total is None:
        return UNKNOWN_TEXT
    return format_kamas(row.runes_value.total) + (PARTIAL_SUFFIX if row.runes_value.partial else "")


def plus_value_tag(plus_value: float | None) -> str | None:
    """The colour tag of a plus-value row."""
    if plus_value is None:
        return None
    return TAG_UP if round(plus_value) >= 0 else TAG_DOWN


def price_text(price: float | None, modified: bool) -> str:
    """A price, marked when the player typed it."""
    return format_kamas(price) + (MODIFIED_SUFFIX if modified and price is not None else "")
