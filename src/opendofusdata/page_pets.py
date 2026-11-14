"""The Familiers page: experience given by one resource, its price and the kamas spent per XP."""

import sqlite3
from datetime import timedelta

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.item_search import search_items
from opendofusdata.pet_manual_form import PetManualForm
from opendofusdata.pet_manual_store import add_manual, load_manual, remove_manual
from opendofusdata.pets_view_data import PetDetail, PetRow, PetUpgrade, pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, local_text
from opendofusdata.timeutil import format_utc
from opendofusdata.ui_chart import ChartPoint, DatedChart
from opendofusdata.ui_stats import StatList, StatRow
from opendofusdata.ui_table import TAG_UP, Column
from opendofusdata.ui_theme import ERROR_COLOR, SUCCESS_COLOR, CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import UNKNOWN_TEXT, format_experience_per_unit, format_kamas, format_kamas_per_experience
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Familiers"
COLUMNS = (Column("Ressource", 200), Column("Type", 120), Column("Prix ×100 / ×1000", 160, True),
           Column("Prix moyen", 110, True), Column("XP pour 1 ressource", 150, True),
           Column("Kamas par XP", 110, True), Column("Observations", 130, True),
           Column("Coût pour monter un familier", 190, True))
KAMAS_PER_XP_COLUMN = 5
BEST_ROW_COUNT = 3
UNRELIABLE_SUFFIX = " peu fiable"
MANUAL_SUFFIX = " + saisi"
STALE_SUFFIX = " (ancien)"
FRESH_PRICE_HOURS = 24  # a x100 / x1000 price older than this is replaced by the last sale price
MAX_KAMAS_PER_XP = 25  # a resource costing more than this per XP point is not worth buying
NO_SELECTION_TEXT = "Sélectionne une ressource pour voir ses relevés."


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
        return (label, f"{format_kamas(stop)} kamas", None)
    exceeded = row.unit_price > stop
    return (label, f"{format_kamas(stop)} kamas" + (" — dépassé" if exceeded else ""),
            ERROR_COLOR if exceeded else SUCCESS_COLOR)


def best_keys(rows: list[PetRow]) -> set[int]:
    """The resources with the lowest known kamas per XP."""
    priced = sorted((row for row in rows if row.kamas_per_xp is not None), key=lambda row: row.kamas_per_xp)
    return {row.item_id for row in priced[:BEST_ROW_COUNT]}


def upgrade_text(upgrade: PetUpgrade) -> str:
    """One upgrade line: exact local date, pet, units and experience."""
    gain = "sans XP" if upgrade.gain is None else f"+{upgrade.gain} XP"
    return f"{local_text(upgrade.moment)}   {upgrade.pet_name}   ×{upgrade.units}, {gain}"


class PetsPage(ViewPage):
    """Resources table and the observed upgrades of the selected one."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (KAMAS_PER_XP_COLUMN, False), 0, **options)
        self._mode = ""
        self._build_detail()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.form = PetManualForm(card, self._search_items, self._add_manual, self._remove_manual)
        self.form.pack(fill="x", padx=PADDING, pady=(PADDING, 0))
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.stats_list = StatList(card)
        self.stats_list.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        self.chart = DatedChart(card)
        self.chart.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        self.upgrades_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.upgrades_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def _selection_changed(self, key: object | None) -> None:
        changed = key != self._selected  # the table also reports the kept selection at every refresh
        super()._selection_changed(key)
        if key is not None and changed:
            self.form.prefill(int(key), self._context.name_of(int(key)))

    def _search_items(self, text: str) -> list[tuple[int, str]]:
        return self._read(lambda connection: search_items(connection, text)) or []

    def _add_manual(self, item_id: int, units: int, experience: int) -> bool:
        saved = add_manual(self._context.config_path, item_id, units, experience)
        self.refresh()
        return saved

    def _remove_manual(self, item_id: int) -> bool:
        removed = remove_manual(self._context.config_path, item_id)
        self.refresh()
        return removed

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per resource seen in usable upgrades inside the window."""
        self._mode = price_mode_from_config(load_config(self._context.config_path))
        book = PriceBook.load(connection, server)
        rows = pet_rows(connection, server, window, self._context.name_of, self._context.type_of, book, self._mode,
                        load_manual(self._context.config_path), self._fresh_since())
        best = best_keys(rows)
        return [self._table_row(row, row.item_id in best) for row in rows]

    def _fresh_since(self) -> str:
        return format_utc(self._clock() - timedelta(hours=FRESH_PRICE_HOURS))

    def _table_row(self, row: PetRow, best: bool) -> TableRow:
        cells = (row.name, row.type_name, bulk_text(row), format_kamas(row.sale_price),
                 format_experience_per_unit(row.per_unit), format_kamas_per_experience(row.kamas_per_xp),
                 observations_text(row), format_kamas(row.cost))
        sort_values = (row.name.casefold(), row.type_name, row.bulk_price, row.sale_price, row.per_unit,
                       row.kamas_per_xp, row.feedings, row.cost)
        return TableRow(row.item_id, cells, sort_values, TAG_UP if best else None)

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """Show the upgrades of the selected resource, or reset the panel."""
        detail = None
        if key is not None:
            book = PriceBook.load(connection, server)  # fresh: its price history reads this open connection
            detail = pet_detail(connection, server, int(key), self._context.name_of, self._context.type_of,
                                book, self._mode, load_manual(self._context.config_path), self._fresh_since())
        if detail is None:
            self._clear_detail()
        else:
            self._fill_detail(detail)

    def _clear_detail(self) -> None:
        self.name_label.configure(text=NO_SELECTION_TEXT)
        self.stats_list.set_rows(())
        self.upgrades_label.configure(text="")
        self.chart.clear()

    def _fill_detail(self, detail: PetDetail) -> None:
        row = detail.row
        self.name_label.configure(text=row.name)
        self.stats_list.set_rows([
            ("XP pour 1 ressource", format_experience_per_unit(row.per_unit), None),
            ("Prix d'1 ressource utilisé", f"{format_kamas(row.unit_price)} kamas", None),
            ("Prix moyen", f"{format_kamas(row.sale_price)} kamas", None),
            ("Kamas par XP", format_kamas_per_experience(row.kamas_per_xp), None), stop_row(row),
            ("Coût pour monter un familier", f"{format_kamas(row.cost)} kamas", None)])
        self.chart.set_series([ChartPoint(moment, ratio, f"Prix : {format_kamas(price)} kamas l'unité")
                               for moment, ratio, price in detail.ratio_points], "kamas par XP", 1)
        self.upgrades_label.configure(text="\n".join(upgrade_text(upgrade) for upgrade in detail.upgrades))
