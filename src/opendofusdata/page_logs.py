"""The Logs page: what is being captured right now, filterable by kind, text and period."""

from collections.abc import Callable
from datetime import datetime

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.log_feed import LogEntry, format_log_row
from opendofusdata.log_filters import KIND_ALL, KINDS, filter_entries
from opendofusdata.run_pipeline import utc_now
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import PeriodSelection, period_window
from opendofusdata.ui_period import PeriodBar
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.ui_theme import PADDING, SMALL_PADDING, TITLE_SIZE, TRANSPARENT
from opendofusdata.ui_widgets import make_label
from opendofusdata.window_context import WindowContext

TITLE = "Logs"
COLUMNS = (Column("Heure", 90), Column("Type", 100), Column("Objet", 320), Column("Détail", 140),
           Column("Valeur", 120, True))
SEARCH_PLACEHOLDER = "Rechercher un objet"
CLEAR_LABEL = "Vider"
SEARCH_WIDTH = 240


class LogsPage:
    """A live table of the captured records; Vider empties only this list, never the database."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext,
                 clock: Callable[[], datetime] = utc_now) -> None:
        self._context, self._clock = context, clock
        self._shown: list[LogEntry] = []
        self._names_used = context.name_of
        self._dirty = True
        self.frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._build_header()
        self.period_bar = PeriodBar(self.frame, self._mark_dirty, PeriodSelection())
        self.period_bar.pack(fill="x", padx=PADDING, pady=(0, SMALL_PADDING))
        self.table = DataTable(self.frame, COLUMNS, lambda key: None, (0, True))
        self.table.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

    def _build_header(self) -> None:
        header = customtkinter.CTkFrame(self.frame, fg_color=TRANSPARENT, corner_radius=0)
        header.pack(fill="x", padx=PADDING, pady=PADDING)
        make_label(header, TITLE, TITLE_SIZE, bold=True).pack(side="left")
        customtkinter.CTkButton(header, text=CLEAR_LABEL, width=80, command=self.clear).pack(side="right")
        self.search_entry = customtkinter.CTkEntry(header, width=SEARCH_WIDTH, placeholder_text=SEARCH_PLACEHOLDER)
        self.search_entry.pack(side="right", padx=SMALL_PADDING)
        self.search_entry.bind("<KeyRelease>", lambda _event: self._mark_dirty())
        self.kind_buttons = customtkinter.CTkSegmentedButton(header, values=list(KINDS),
                                                             command=lambda _kind: self._mark_dirty())
        self.kind_buttons.set(KIND_ALL)
        self.kind_buttons.pack(side="left", padx=PADDING)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.render(None)

    def clear(self) -> None:
        """Empty the list (the stored data is kept)."""
        self._context.session.feed.clear()
        self._mark_dirty()

    def _filtered(self) -> list[LogEntry]:
        window = period_window(self.period_bar.selection(), self._clock())
        return filter_entries(self._context.session.feed.entries(), self.search_entry.get(),
                              self.kind_buttons.get(), window, self._context.name_of)

    def render(self, snapshot: SessionSnapshot | None) -> None:
        """Rewrite the table only when the filtered entries (or the names) changed."""
        entries, names = self._filtered(), self._context.name_of
        if not self._dirty and entries == self._shown and names is self._names_used:
            return
        self._dirty = False
        self._shown, self._names_used = entries, names
        self.table.set_rows([self._row(index, entry, names) for index, entry in enumerate(entries)])

    @staticmethod
    def _row(index: int, entry: LogEntry, names: Callable[[int], str]) -> TableRow:
        cells = format_log_row(entry, names)
        return TableRow(index, cells, (entry.moment, *cells[1:]))
