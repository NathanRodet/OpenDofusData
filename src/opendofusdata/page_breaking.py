"""The Brisage page: the broken objects, the breakings of the selected one, and the detail of the object or breaking."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.breaking_detail_data import breaking_detail, item_tabs, mean_coefficient
from opendofusdata.breaking_detail_text import BREAKING_KEY
from opendofusdata.breaking_items import ItemSummary, group_by_item, item_summaries
from opendofusdata.breaking_panel import BreakingPanel
from opendofusdata.breaking_texts import coefficient_text, plus_value_tag, runes_text, runes_list_text
from opendofusdata.breaking_view_data import BreakingRow, breaking_rows
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.effects_csv import EFFECTS_FILE, RUNES_FILE, ItemEffects, Rune, load_item_effects, load_runes
from opendofusdata.price_book import PriceBook
from opendofusdata.price_rules import PRICE_LAST
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.ui_theme import PADDING, SMALL_PADDING, WIDE_DETAIL_WIDTH
from opendofusdata.ui_theme import CARD_TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Brisage"
ITEM_COLUMNS = (Column("Objet", 230), Column("Prix HDV", 100, True), Column("Coef.", 80, True),
                Column("Plus-value", 110, True), Column("Brisages", 90, True))
BREAKING_COLUMNS = (Column("Il y a", 90), Column("Qté", 55, True), Column("Coef.", 70, True),
                    Column("Runes obtenues", 270), Column("Valeur", 90, True), Column("Plus-value", 100, True))
PLUS_VALUE_COLUMN = 3
BREAKINGS_TITLE = "Brisages de {name}"
BREAKINGS_HINT = "Clique sur un brisage pour voir ses runes."
NO_EFFECTS_TEXT = "Effets de l'objet inconnus : clique sur « Télécharger les données de référence » dans Réglages."
BREAKING_NOTE = "{when}, {quantity} objet(s) brisé(s) à {coefficient}"


class BreakingPage(ViewPage):
    """Left: broken objects, then the breakings of the selected one. Right: tabs for the object or the breaking."""

    detail_width = WIDE_DETAIL_WIDTH

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, ITEM_COLUMNS, (PLUS_VALUE_COLUMN, True), 0, **options)
        self._by_item: dict[int, list[BreakingRow]] = {}
        self._effects: dict[int, ItemEffects] | None = None
        self._effects_generation = -1
        self._runes: list[Rune] = []
        self._detail_item: object = None
        self._chosen_breaking: str | None = None
        self._wanted_tab: str | None = None
        self.breakings_title = make_label(self.split.main, BREAKINGS_TITLE.format(name="l'objet sélectionné"),
                                          CARD_TITLE_SIZE, bold=True, anchor="w")
        self.breakings_title.pack(fill="x", pady=(PADDING, SMALL_PADDING))
        self.breakings_table = DataTable(self.split.main, BREAKING_COLUMNS, self._breaking_selected, (0, True))
        self.breakings_table.pack(fill="both", expand=True)
        self.panel = BreakingPanel(self.split.detail)
        self.panel.pack(fill="both", expand=True)

    def _load_data(self) -> None:
        if self._effects is None or self._effects_generation != self._context.reference_generation:
            self._effects_generation = self._context.reference_generation
            directory = self._context.data_directory
            self._effects = load_item_effects(directory / EFFECTS_FILE) or load_item_effects("data/" + EFFECTS_FILE)
            self._runes = load_runes(directory / RUNES_FILE) or load_runes("data/" + RUNES_FILE)

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per broken object inside the window."""
        mode = price_mode_from_config(load_config(self._context.config_path))
        book = PriceBook.load(connection, server)
        rows = breaking_rows(connection, server, window, self._context.name_of, book, mode)
        self._by_item = group_by_item(rows)
        summaries = item_summaries(rows, lambda item_id: book.unit_price(item_id, PRICE_LAST))
        return [self._item_row(summary) for summary in summaries]

    def _item_row(self, summary: ItemSummary) -> TableRow:
        cells = (summary.name, format_kamas(summary.hdv_price), coefficient_text(summary.coefficient),
                 format_signed_kamas(summary.plus_value), str(summary.breakings))
        sort_values = (summary.name.casefold(), summary.hdv_price, summary.coefficient, summary.plus_value,
                       summary.breakings)
        return TableRow(summary.item_id, cells, sort_values, plus_value_tag(summary.plus_value))

    def _breaking_row(self, key: str, row: BreakingRow, now: datetime) -> TableRow:
        cells = (elapsed_text(row.moment, now), str(row.quantity), coefficient_text(row.coefficient),
                 runes_list_text(row.runes, self._context.name_of), runes_text(row),
                 format_signed_kamas(row.plus_value))
        sort_values = (row.moment, row.quantity, row.coefficient, sum(count for _, count in row.runes),
                       row.runes_value.total, row.plus_value)
        return TableRow(key, cells, sort_values, plus_value_tag(row.plus_value))

    def _breaking_selected(self, key: object | None) -> None:
        chosen = None if key is None else str(key)
        if chosen == self._chosen_breaking:
            return  # the table also reports the kept selection at every refresh
        self._chosen_breaking = chosen
        self._wanted_tab = BREAKING_KEY if chosen is not None else None
        self._refresh_detail()

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """List the breakings of the selected object and fill the panel with its tabs."""
        own = self._by_item.get(key) if key is not None else None
        if key != self._detail_item:
            self._detail_item, self._chosen_breaking, self._wanted_tab = key, None, None
        if not own:
            self.breakings_table.set_rows([])
            self.breakings_title.configure(text=BREAKINGS_TITLE.format(name="l'objet sélectionné"))
            self.panel.clear()
            return
        self._load_data()
        rows = dict(self._keyed(own))
        self.breakings_table.set_rows([self._breaking_row(row_key, row, self._clock()) for row_key, row in rows.items()])
        self.breakings_title.configure(text=BREAKINGS_TITLE.format(name=own[0].name) + f" ({len(own)})")
        self._show_panel(connection, server, own, rows)

    @staticmethod
    def _keyed(own: list[BreakingRow]) -> list[tuple[str, BreakingRow]]:
        """Each breaking with a stable key (its date, numbered when two share the same second)."""
        seen: dict[str, int] = {}
        keyed = []
        for row in own:
            stamp = row.moment.isoformat()
            seen[stamp] = seen.get(stamp, 0) + 1
            keyed.append((f"{stamp}#{seen[stamp]}", row))
        return keyed

    def _show_panel(self, connection: sqlite3.Connection, server: str, own: list[BreakingRow],
                    rows: dict[str, BreakingRow]) -> None:
        book = PriceBook.load(connection, server)
        effects = self._effects.get(own[0].item_id)
        name_of = self._context.name_of
        tabs = item_tabs(own, effects, self._runes, book, name_of)
        chosen = rows.get(self._chosen_breaking) if self._chosen_breaking else None
        if chosen is not None:
            note = BREAKING_NOTE.format(when=elapsed_text(chosen.moment, self._clock()), quantity=chosen.quantity,
                                        coefficient=coefficient_text(chosen.coefficient))
            tabs.insert(0, breaking_detail(chosen, effects, self._runes, book, name_of, note))
        info = f"Coefficient moyen {coefficient_text(mean_coefficient(own))}, {len(own)} brisage(s). {BREAKINGS_HINT}"
        self.panel.show(own[0].name, info, tabs, "" if effects else NO_EFFECTS_TEXT, self._wanted_tab)
        self._wanted_tab = None
