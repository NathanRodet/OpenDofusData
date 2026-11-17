"""The HDV page: every item with its latest price, and a detail with dated price curves."""

import sqlite3

import customtkinter

from opendofusdata.hdv_view_data import HdvDetail, hdv_detail, hdv_rows
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import Window, elapsed_text, local_text, parse_stored
from opendofusdata.ui_chart import ChartPoint, DatedChart
from opendofusdata.ui_history import HistoryList
from opendofusdata.ui_stats import StatList, StatRow
from opendofusdata.ui_table import Column
from opendofusdata.ui_theme import (
    CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING,
    TITLE_SIZE,
)
from opendofusdata.ui_widgets import make_card_title, make_label
from opendofusdata.value_format import UNKNOWN_TEXT, format_kamas
from opendofusdata.view_page import ViewPage
from opendofusdata.window_context import WindowContext

TITLE = "HDV"
COLUMNS = (Column("Objet", 220), Column("Type", 130), Column("Dernier prix ×1", 120, True),
           Column("Médian 24 h", 110, True), Column("Vendus 24 h", 100, True), Column("Dernier relevé", 120, True))
LAST_SEEN_COLUMN = 5
CHART_PERIODS = {"24 h": "24h", "7 j": "7d", "30 j": "30d"}
NO_SELECTION_TEXT = "Sélectionne un objet pour voir son détail."
LOTS_TITLE = "Prix par lot"
HISTORY_TITLE = "Derniers relevés"
NO_FIGURE_TEXT = "-"


def _number_text(value: int | None) -> str:
    return UNKNOWN_TEXT if value is None else format_kamas(float(value))


def _kamas_text(value: int | None) -> str:
    """An amount of kamas for the detail list ('Inconnu' alone when it was never seen)."""
    return UNKNOWN_TEXT if value is None else f"{format_kamas(float(value))} kamas"


def _cell_text(value: int | None) -> str:
    """A table cell: a dash when the figure was never seen (market statistics exist only for opened items)."""
    return NO_FIGURE_TEXT if value is None else format_kamas(float(value))


class HdvPage(ViewPage):
    """HDV table (left or top) and item detail (right or bottom)."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, **options: object) -> None:
        super().__init__(parent, context, TITLE, COLUMNS, (LAST_SEEN_COLUMN, True), 0, **options)
        self._detail: HdvDetail | None = None
        self._chart_period = "24h"
        self._build_detail()

    def _build_detail(self) -> None:
        card = customtkinter.CTkScrollableFrame(self.split.detail, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True)
        self.name_label = make_label(card, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", wraplength=300)
        self.name_label.pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.type_label = make_label(card, "", color=MUTED_COLOR, anchor="w")
        self.type_label.pack(fill="x", padx=PADDING)
        self.stats_list = StatList(card)
        self.stats_list.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        tabs = customtkinter.CTkSegmentedButton(card, values=list(CHART_PERIODS), command=self._tab_chosen)
        tabs.set("24 h")
        tabs.pack(padx=PADDING, pady=(SMALL_PADDING, 0), anchor="w")
        self.chart = DatedChart(card)
        self.chart.pack(fill="x", padx=PADDING, pady=SMALL_PADDING)
        make_card_title(card, LOTS_TITLE).pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.lots_list = StatList(card)
        self.lots_list.pack(fill="x", padx=PADDING)
        self._build_history(card)

    def _build_history(self, card: customtkinter.CTkBaseClass) -> None:
        make_card_title(card, HISTORY_TITLE).pack(fill="x", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.history_list = HistoryList(card)
        self.history_list.pack(fill="x", padx=PADDING, pady=(0, PADDING))

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """One row per item captured inside the window."""
        now = self._clock()
        rows = hdv_rows(connection, server, window, self._context.name_of, self._context.type_of)
        return [TableRow(row.item_id, (row.name, row.type_name, _cell_text(row.last_price),
                                       _cell_text(row.median_24h), _cell_text(row.sold_24h),
                                       elapsed_text(row.last_seen, now)),
                         (row.name.casefold(), row.type_name, row.last_price, row.median_24h, row.sold_24h,
                          row.last_seen)) for row in rows]

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """Fill the detail of the selected item, or reset it."""
        if key is None:
            self._detail = None
        else:
            self._detail = hdv_detail(connection, server, int(key), self._context.name_of, self._context.type_of)
        self._draw_detail()

    def _tab_chosen(self, label: str) -> None:
        self._chart_period = CHART_PERIODS[label]
        self._draw_detail()

    def _draw_detail(self) -> None:
        detail = self._detail
        if detail is None:
            self.name_label.configure(text=NO_SELECTION_TEXT)
            self.type_label.configure(text="")
            self.stats_list.set_rows(())
            self.lots_list.set_rows(())
            self.chart.clear()
            self.history_list.set_rows(())
            return
        self.name_label.configure(text=detail.name)
        self.type_label.configure(text=detail.type_name)
        self.lots_list.set_rows([(f"Lot ×{size}", f"{format_kamas(price)} kamas", None)
                                 for size, price in sorted(detail.lots.items())])
        self._draw_chart(detail)
        self._draw_history(detail)

    def _stat_rows(self, detail: HdvDetail, last_seen: str) -> list[StatRow]:
        median, mean, sold = detail.stats.get(self._chart_period, (None, None, None))
        rows: list[StatRow] = [("Médian", _kamas_text(median), None),
                               ("Moyen", _kamas_text(mean), None), ("Vendus", _number_text(sold), None)]
        return rows + ([("Dernier relevé", last_seen, None)] if last_seen else [])

    def _draw_chart(self, detail: HdvDetail) -> None:
        curve = detail.curves.get(self._chart_period, [])
        self.chart.set_series([ChartPoint(point.moment, point.price, f"{point.quantity} objets vendus")
                               for point in curve], "kamas")

    def _draw_history(self, detail: HdvDetail) -> None:
        rows = [(local_text(parse_stored(lot.captured_at)), f"Lot ×{lot.lot_size}", f"{format_kamas(lot.price)} kamas")
                for lot in detail.history]
        last = local_text(parse_stored(detail.history[0].captured_at)) if detail.history else ""
        self.stats_list.set_rows(self._stat_rows(detail, last))
        self.history_list.set_rows(rows)
