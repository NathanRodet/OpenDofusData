"""The Familiers page: experience given by one resource, its price and the kamas spent per XP."""

import sqlite3
from datetime import timedelta

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.item_search import search_items
from opendofusdata.pet_coverage import Coverage, load_coverage
from opendofusdata.pet_coverage_view import CoverageView
from opendofusdata.pet_manual_form import PetManualForm
from opendofusdata.pet_manual_store import add_manual, load_manual, remove_manual
from opendofusdata.pet_favorites_store import load_favorites, toggle_favorite
from opendofusdata.pets_texts import (FAVORITE_MARK, best_keys, bulk_text, kamas_line, observations_text, stop_row,
                                      upgrade_row)
from opendofusdata.pets_view_data import PetDetail, PetRow, pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window
from opendofusdata.timeutil import format_utc
from opendofusdata.ui_history import HistoryList
from opendofusdata.ui_stats import StatList
from opendofusdata.ui_table import TAG_UP, Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, PADDING, SMALL_PADDING, TITLE_SIZE, TRANSPARENT
from opendofusdata.ui_widgets import make_card_title, make_label
from opendofusdata.value_format import format_experience_per_unit, format_kamas, format_kamas_per_experience
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Familiers"
TAB_RESOURCES = "Ressources"
FAVORITE_LABEL = "Ressource favorite"
FAVORITES_ONLY_LABEL = "Favoris seulement"
TAB_COVERAGE = "Couverture"
COLUMNS = (Column("Ressource", 200), Column("Type", 120), Column("Prix ×100 / ×1000", 160, True),
           Column("Prix moyen", 110, True), Column("XP pour 1 ressource", 150, True),
           Column("Kamas par XP", 110, True), Column("Observations", 130, True),
           Column("Coût pour monter un familier", 190, True))
KAMAS_PER_XP_COLUMN = 5
FRESH_PRICE_HOURS = 24  # a x100 / x1000 price older than this is replaced by the last sale price
NO_SELECTION_TEXT = "Sélectionne une ressource pour voir ses relevés."
HISTORY_TITLE = "Derniers relevés"


class PetsPage(ViewPage):
    """Resources table and the observed upgrades of the selected one."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (KAMAS_PER_XP_COLUMN, False), 0, **options)
        self._mode = ""
        self._coverage = Coverage(0, 0, ())
        self._favorites: set[int] = set()
        self._build_detail()
        self._build_tabs()

    def _build_tabs(self) -> None:
        self.coverage_view = CoverageView(self.frame)
        bar = customtkinter.CTkFrame(self.frame, fg_color=TRANSPARENT, corner_radius=0)
        bar.pack(before=self.split, fill="x", padx=PADDING, pady=(0, SMALL_PADDING))
        self.tabs = customtkinter.CTkSegmentedButton(bar, values=[TAB_RESOURCES, TAB_COVERAGE], command=self._tab_chosen)
        self.tabs.set(TAB_RESOURCES)
        self.tabs.pack(side="left")
        self.favorites_only = customtkinter.CTkCheckBox(bar, text=FAVORITES_ONLY_LABEL, command=self._show_rows)
        self.favorites_only.pack(side="left", padx=PADDING)

    def _tab_chosen(self, tab: str) -> None:
        if tab == TAB_COVERAGE:
            self.split.pack_forget()
            self.coverage_view.pack(fill="both", expand=True)
        else:
            self.coverage_view.pack_forget()
            self.split.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

    def _show_rows(self) -> None:
        every_row = self._rows
        if self.favorites_only.get():
            self._rows = [row for row in every_row if row.key in self._favorites]
        super()._show_rows()
        self._rows = every_row
        self.coverage_view.set_coverage(self._coverage, self.search_entry.get())

    def _toggle_favorite(self) -> None:
        if self._selected is not None:
            toggle_favorite(self._context.config_path, int(self._selected))
            self.refresh()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.form = PetManualForm(card, self._search_items, self._add_manual, self._remove_manual)
        self.form.pack(fill="x", padx=PADDING, pady=(PADDING, 0))
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.favorite_box = customtkinter.CTkCheckBox(card, text=FAVORITE_LABEL, command=self._toggle_favorite)
        self.favorite_box.pack(anchor="w", padx=PADDING)
        self.stats_list = StatList(card)
        self.stats_list.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        make_card_title(card, HISTORY_TITLE).pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.history_list = HistoryList(card)
        self.history_list.pack(fill="x", padx=PADDING, pady=(0, PADDING))

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
        self._favorites = load_favorites(self._context.config_path)
        self._coverage = load_coverage(connection, {row.item_id for row in rows if row.per_unit is not None})
        best = best_keys(rows)
        return [self._table_row(row, row.item_id in best) for row in rows]

    def _fresh_since(self) -> str:
        return format_utc(self._clock() - timedelta(hours=FRESH_PRICE_HOURS))

    def _table_row(self, row: PetRow, best: bool) -> TableRow:
        name = (FAVORITE_MARK if row.item_id in self._favorites else "") + row.name
        cells = (name, row.type_name, bulk_text(row), format_kamas(row.sale_price),
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
        self.favorite_box.deselect()
        self.favorite_box.configure(state="disabled")
        self.stats_list.set_rows(())
        self.history_list.set_rows(())

    def _fill_detail(self, detail: PetDetail) -> None:
        row = detail.row
        self.name_label.configure(text=row.name)
        self.favorite_box.configure(state="normal")
        (self.favorite_box.select if row.item_id in self._favorites else self.favorite_box.deselect)()
        self.stats_list.set_rows([
            ("XP pour 1 ressource", format_experience_per_unit(row.per_unit), None),
            ("Prix d'1 ressource utilisé", kamas_line(row.unit_price), None),
            ("Prix moyen", kamas_line(row.sale_price), None),
            ("Kamas par XP", format_kamas_per_experience(row.kamas_per_xp), None), stop_row(row),
            ("Coût pour monter un familier", kamas_line(row.cost), None)])
        self.history_list.set_rows([upgrade_row(upgrade) for upgrade in detail.upgrades])
