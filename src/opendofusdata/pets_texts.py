"""The texts and rules of the Familiers table and detail: pure helpers."""

from opendofusdata.pets_view_data import PetRow, PetUpgrade
from opendofusdata.time_filters import local_text
from opendofusdata.ui_history import HistoryRow
from opendofusdata.ui_stats import StatRow
from opendofusdata.ui_theme import ERROR_COLOR, SUCCESS_COLOR
from opendofusdata.value_format import UNKNOWN_TEXT, format_kamas

BEST_ROW_COUNT = 3
UNRELIABLE_SUFFIX = " peu fiable"
MANUAL_SUFFIX = " + saisi"
STALE_SUFFIX = " (ancien)"
FAVORITE_MARK = "\u2605 "
MAX_KAMAS_PER_XP = 25  # a resource costing more than this per XP point is not worth buying


def kamas_line(value: float | None) -> str:
    """An amount of kamas for the detail list ('Inconnu' alone when it was never seen)."""
    return UNKNOWN_TEXT if value is None else f"{format_kamas(value)} kamas"


def observations_text(row: PetRow) -> str:
    """The number of feedings, marked when too little experience was observed."""
    return str(row.feedings) + ("" if row.reliable else UNRELIABLE_SUFFIX) + (MANUAL_SUFFIX if row.manual else "")


def bulk_text(row: PetRow) -> str:
    """The x100 / x1000 price, marked when it is too old to be used."""
    return format_kamas(row.bulk_price) + (STALE_SUFFIX if row.bulk_stale else "")


def stop_row(row: PetRow) -> StatRow:
    """The highest price of one resource worth paying (stop at MAX_KAMAS_PER_XP per XP), green or red."""
    label = f"Stop ({MAX_KAMAS_PER_XP} kamas par XP)"
    if row.per_unit is None or row.per_unit <= 0:
        return (label, UNKNOWN_TEXT, None)
    stop = MAX_KAMAS_PER_XP * row.per_unit
    if row.unit_price is None:
        return (label, kamas_line(stop), None)
    exceeded = row.unit_price > stop
    return (label, f"{format_kamas(stop)} kamas" + (", dépassé" if exceeded else ""),
            ERROR_COLOR if exceeded else SUCCESS_COLOR)


def best_keys(rows: list[PetRow]) -> set[int]:
    """The resources with the lowest known kamas per XP."""
    priced = sorted((row for row in rows if row.kamas_per_xp is not None), key=lambda row: row.kamas_per_xp)
    return {row.item_id for row in priced[:BEST_ROW_COUNT]}


def upgrade_row(upgrade: PetUpgrade) -> HistoryRow:
    """One history row: local date, pet, then units and experience."""
    gain = "sans XP" if upgrade.gain is None else f"+{upgrade.gain} XP"
    return (local_text(upgrade.moment), upgrade.pet_name, f"×{upgrade.units}, {gain}")
