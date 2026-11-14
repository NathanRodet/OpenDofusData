"""The Familiers page: experience given by one resource, its price and the kamas spent per XP."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.item_search import search_items
from opendofusdata.pet_manual_form import PetManualForm
from opendofusdata.pet_manual_store import add_manual, load_manual, remove_manual
from opendofusdata.pets_view_data import PetDetail, PetRow, PetUpgrade, pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text, local_text
from opendofusdata.ui_chart import ChartPoint, DatedChart
from opendofusdata.ui_table import TAG_UP, Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import format_experience_per_unit, format_kamas, format_kamas_per_experience
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Familiers"
COLUMNS = (Column("Ressource", 200), Column("Type", 120), Column("Prix d'1 ressource", 130, True),
           Column("XP pour 1 ressource", 150, True), Column("Kamas par XP", 110, True),
           Column("Observations", 130, True), Column("Dernier relevé", 120, True),
           Column("Coût pour monter un familier", 190, True))
KAMAS_PER_XP_COLUMN = 4
BEST_ROW_COUNT = 3
UNRELIABLE_SUFFIX = " peu fiable"
MANUAL_SUFFIX = " + saisi"
NO_SELECTION_TEXT = "Sélectionne une ressource pour voir ses relevés."


def observations_text(row: PetRow) -> str:
    """The number of feedings, marked when too little experience was observed."""
    return str(row.feedings) + ("" if row.reliable else UNRELIABLE_SUFFIX) + (MANUAL_SUFFIX if row.manual else "")


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
        self.tiles_label = make_label(card, "", anchor="w", justify="left")
        self.tiles_label.pack(fill="x", padx=PADDING)
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
                        load_manual(self._context.config_path))
        best, now = best_keys(rows), self._clock()
        return [self._table_row(row, now, row.item_id in best) for row in rows]

    def _table_row(self, row: PetRow, now: datetime, best: bool) -> TableRow:
        seen = elapsed_text(row.last_seen, now) if row.last_seen else ""
        cells = (row.name, row.type_name, format_kamas(row.unit_price), format_experience_per_unit(row.per_unit),
                 format_kamas_per_experience(row.kamas_per_xp), observations_text(row), seen, format_kamas(row.cost))
        sort_values = (row.name.casefold(), row.type_name, row.unit_price, row.per_unit, row.kamas_per_xp,
                       row.feedings, row.last_seen, row.cost)
        return TableRow(row.item_id, cells, sort_values, TAG_UP if best else None)

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """Show the upgrades of the selected resource, or reset the panel."""
        detail = None
        if key is not None:
            book = PriceBook.load(connection, server)  # fresh: its price history reads this open connection
            detail = pet_detail(connection, server, int(key), self._context.name_of, self._context.type_of,
                                book, self._mode, load_manual(self._context.config_path))
        if detail is None:
            self._clear_detail()
        else:
            self._fill_detail(detail)

    def _clear_detail(self) -> None:
        self.name_label.configure(text=NO_SELECTION_TEXT)
        self.tiles_label.configure(text="")
        self.upgrades_label.configure(text="")
        self.chart.clear()

    def _fill_detail(self, detail: PetDetail) -> None:
        row = detail.row
        self.name_label.configure(text=row.name)
        self.tiles_label.configure(text=(
            f"XP pour 1 ressource : {format_experience_per_unit(row.per_unit)}\n"
            f"Prix d'1 ressource : {format_kamas(row.unit_price)} kamas\n"
            f"Kamas par XP : {format_kamas_per_experience(row.kamas_per_xp)}\n"
            f"Coût pour monter un familier : {format_kamas(row.cost)} kamas"))
        self.chart.set_series([ChartPoint(moment, ratio, f"Prix : {format_kamas(price)} kamas l'unité")
                               for moment, ratio, price in detail.ratio_points], "kamas par XP", 1)
        self.upgrades_label.configure(text="\n".join(upgrade_text(upgrade) for upgrade in detail.upgrades))
