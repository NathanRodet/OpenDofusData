"""Brisage tab 1: current HDV price (editable) and the kamas a breaking could bring, per object."""

import sqlite3
from datetime import datetime

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.breaking_simulation import SimulationRow, simulate
from opendofusdata.breaking_texts import MODIFIED_SUFFIX, coefficient_text, plus_value_tag, price_text
from opendofusdata.breaking_view_data import BreakingDetail, BreakingRow, breaking_detail, breaking_rows
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, local_text
from opendofusdata.ui_chart import ChartPoint, DatedChart
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.user_prices import HDV_OVERRIDES_KEY, load_prices, parse_kamas, store_price
from opendofusdata.value_format import format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Prix de l'HDV actuel et kamas potentiels"
COLUMNS = (Column("Objet", 220), Column("Prix HDV (double-clic pour modifier)", 230, True),
           Column("Coefficient moyen", 140, True), Column("Brisages", 90, True),
           Column("Valeur moyenne des runes", 190, True), Column("Valeur max des runes", 170, True),
           Column("Plus-value moyenne", 160, True), Column("Plus-value max", 140, True))
PRICE_COLUMN = 1
PLUS_VALUE_COLUMN = 6
NO_SELECTION_TEXT = "Sélectionne un objet pour voir l'historique de son coefficient."
BAD_PRICE_NOTICE = "Prix illisible : écris un nombre (95000, 95 000, 1,5k). Vide = reprendre le prix de l'HDV."
SAVE_FAILED_NOTICE = "Le prix n'a pas pu être enregistré (voir le journal)."


class SimulationPage(ViewPage):
    """One row per broken object; the HDV price can be typed to simulate a craft or a purchase."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (PLUS_VALUE_COLUMN, True), 0,
                         editable=(PRICE_COLUMN,), on_edit=self.price_typed, **options)
        self._breaking_rows: list[BreakingRow] = []
        self._book: PriceBook | None = None
        self._mode = ""
        self._build_detail()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.tiles_label = make_label(card, "", anchor="w", justify="left")
        self.tiles_label.pack(fill="x", padx=PADDING)
        self.chart = DatedChart(card)
        self.chart.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        self.runes_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.runes_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def price_typed(self, key: object, column: int, text: str) -> None:
        """Save the HDV price typed for an object (empty text goes back to the HDV price)."""
        try:
            price = parse_kamas(text.replace(MODIFIED_SUFFIX, ""))
        except ValueError:
            self.notice.configure(text=BAD_PRICE_NOTICE)
            return
        saved = store_price(self._context.config_path, HDV_OVERRIDES_KEY, str(key), price)
        self.notice.configure(text="" if saved else SAVE_FAILED_NOTICE)
        self.refresh()

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per broken object inside the window, valued with the chosen price mode."""
        self._mode = price_mode_from_config(load_config(self._context.config_path))
        self._book = PriceBook.load(connection, server)
        self._breaking_rows = breaking_rows(connection, server, window, self._context.name_of, self._book,
                                            self._mode)
        overrides = {int(name): price for name, price in load_prices(self._context.config_path,
                                                                     HDV_OVERRIDES_KEY).items() if name.isdigit()}
        return [self._table_row(row) for row in simulate(self._breaking_rows, overrides)]

    @staticmethod
    def _table_row(row: SimulationRow) -> TableRow:
        cells = (row.name, price_text(row.hdv_price, row.overridden), coefficient_text(row.mean_coefficient),
                 str(row.count), format_kamas(row.mean_runes_value), format_kamas(row.best_runes_value),
                 format_signed_kamas(row.mean_plus_value), format_signed_kamas(row.best_plus_value))
        sort_values = (row.name.casefold(), row.hdv_price, row.mean_coefficient, row.count, row.mean_runes_value,
                       row.best_runes_value, row.mean_plus_value, row.best_plus_value)
        return TableRow(row.item_id, cells, sort_values, plus_value_tag(row.mean_plus_value))

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """Show the coefficient history of the selected object, or reset the panel."""
        detail = None
        if key is not None and self._book is not None:
            detail = breaking_detail(self._breaking_rows, int(key), self._context.name_of, self._book, self._mode)
        if detail is None:
            self._clear_detail()
        else:
            self._fill_detail(detail)

    def _clear_detail(self) -> None:
        self.name_label.configure(text=NO_SELECTION_TEXT)
        self.tiles_label.configure(text="")
        self.runes_label.configure(text="")
        self.chart.clear()

    def _fill_detail(self, detail: BreakingDetail) -> None:
        self.name_label.configure(text=detail.name)
        self.tiles_label.configure(text=(f"Dernier : {coefficient_text(detail.last_coefficient)}\n"
                                         f"Moyen : {coefficient_text(detail.mean_coefficient)}\n"
                                         f"Brisages : {detail.count}"))
        self.chart.set_series([ChartPoint(moment, coefficient * 100, f"{runes} runes obtenues")
                               for moment, coefficient, runes in detail.points], "%")
        lines = [f"Dernier brisage : {local_text(detail.last_row.moment)}"]
        lines += [f"{name} ×{quantity} : {format_kamas(price)} kamas l'unité"
                  for name, quantity, price in detail.last_runes]
        self.runes_label.configure(text="\n".join(lines))
