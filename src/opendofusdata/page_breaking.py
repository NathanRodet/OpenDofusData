"""The Brisage page: every broken object with its coefficient, rune value and plus-value."""

import sqlite3

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.breaking_view_data import BreakingDetail, BreakingRow, breaking_detail, breaking_rows
from opendofusdata.client_settings import price_mode_from_config
from opendofusdata.price_book import PriceBook
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text, local_text
from opendofusdata.ui_chart import ChartPoint, DatedChart
from opendofusdata.ui_table import TAG_DOWN, TAG_UP, Column
from opendofusdata.ui_theme import CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import UNKNOWN_TEXT, format_kamas, format_signed_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "Brisage"
COLUMNS = (Column("Il y a", 100), Column("Objet", 200), Column("Quantité", 80, True), Column("Coefficient", 90, True),
           Column("Valeur estimée de l'objet", 170, True), Column("Valeur HDV de l'objet", 160, True),
           Column("Valeur estimée des runes", 170, True), Column("Plus-value", 110, True))
PLUS_VALUE_COLUMN = 7
NAME_COLUMN = 1
PERCENT = 100
PARTIAL_SUFFIX = " partielle"
NO_SELECTION_TEXT = "Sélectionne un objet pour voir l'historique de son coefficient."


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


class BreakingPage(ViewPage):
    """Breaking table and the coefficient history of the selected object."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (PLUS_VALUE_COLUMN, True), NAME_COLUMN, **options)
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

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per broken object inside the window, valued with the chosen price mode."""
        self._mode = price_mode_from_config(load_config(self._context.config_path))
        self._book = PriceBook.load(connection, server)
        self._breaking_rows = breaking_rows(connection, server, window, self._context.name_of, self._book,
                                            self._mode)
        now = self._clock()
        return [self._table_row(row, now) for row in self._breaking_rows]

    def _table_row(self, row: BreakingRow, now) -> TableRow:
        cells = (elapsed_text(row.moment, now), row.name, str(row.quantity), coefficient_text(row.coefficient),
                 format_kamas(row.estimated_value), format_kamas(row.hdv_value), runes_text(row),
                 format_signed_kamas(row.plus_value))
        sort_values = (row.moment, row.name.casefold(), row.quantity, row.coefficient, row.estimated_value,
                       row.hdv_value, row.runes_value.total, row.plus_value)
        return TableRow(row.item_id, cells, sort_values, plus_value_tag(row.plus_value))

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
        self.chart.set_series([ChartPoint(moment, coefficient * PERCENT, f"{runes} runes obtenues")
                               for moment, coefficient, runes in detail.points], "%")
        self.runes_label.configure(text=self._last_breaking_text(detail))

    def _last_breaking_text(self, detail: BreakingDetail) -> str:
        row = detail.last_row
        lines = [f"Dernier brisage : {local_text(row.moment)}"]
        lines += [f"{name} ×{quantity} : {format_kamas(price)} kamas l'unité" for name, quantity, price
                  in detail.last_runes]
        lines += [f"Valeur estimée des runes : {runes_text(row)}",
                  f"Valeur estimée de l'objet : {format_kamas(row.estimated_value)}",
                  f"Valeur HDV de l'objet : {format_kamas(row.hdv_value)}",
                  f"Plus-value : {format_signed_kamas(row.plus_value)}"]
        return "\n".join(lines)
