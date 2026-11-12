"""The skeleton shared by the data pages: title, search, period, table, detail, throttled database reads."""

import logging
import sqlite3
import time
from collections.abc import Callable, Sequence
from datetime import datetime

import customtkinter

from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.run_pipeline import utc_now
from opendofusdata.table_model import TableRow
from opendofusdata.time_filters import PeriodSelection, Window, period_window
from opendofusdata.ui_period import PeriodBar
from opendofusdata.ui_split import SplitLayout
from opendofusdata.ui_table import Column, DataTable
from opendofusdata.ui_theme import MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE, TRANSPARENT
from opendofusdata.ui_widgets import make_label
from opendofusdata.view_connection import open_view_connection
from opendofusdata.window_context import WindowContext

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 2.0
SEARCH_WIDTH = 240
SEARCH_PLACEHOLDER = "Rechercher un objet"
TRUNCATED_NOTICE = "Seules les 5 000 premières lignes sont affichées : affine la période ou la recherche."
READ_FAILED_NOTICE = "Lecture de la base impossible pour le moment, les dernières données restent affichées."


class ViewPage:
    """Reads the database every REFRESH_SECONDS and on every filter or selection change."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, title: str,
                 columns: Sequence[Column], default_sort: tuple[int, bool], name_column: int,
                 monotonic: Callable[[], float] = time.monotonic, clock: Callable[[], datetime] = utc_now) -> None:
        self._context, self._name_column = context, name_column
        self._monotonic, self._clock = monotonic, clock
        self._rows: list[TableRow] = []
        self._last_refresh: float | None = None
        self._server: str | None = None
        self._selected: object | None = None
        self.frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._build_header(title)
        self.split = SplitLayout(self.frame)
        self.split.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))
        self.table = DataTable(self.split.main, columns, self._selection_changed, default_sort)
        self.notice = make_label(self.split.main, "", color=MUTED_COLOR, anchor="w")
        self.notice.pack(side="bottom", fill="x")
        self.table.pack(fill="both", expand=True)

    def _build_header(self, title: str) -> None:
        header = customtkinter.CTkFrame(self.frame, fg_color=TRANSPARENT, corner_radius=0)
        header.pack(fill="x", padx=PADDING, pady=PADDING)
        make_label(header, title, TITLE_SIZE, bold=True).pack(side="left")
        self.search_entry = customtkinter.CTkEntry(header, width=SEARCH_WIDTH, placeholder_text=SEARCH_PLACEHOLDER)
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", lambda _event: self._show_rows())
        self.period_bar = PeriodBar(self.frame, self.refresh, PeriodSelection())
        self.period_bar.pack(fill="x", padx=PADDING, pady=(0, SMALL_PADDING))

    def load_rows(self, connection: sqlite3.Connection, server: str, window: Window) -> list[TableRow]:
        """The table rows of the view; implemented by each page."""
        raise NotImplementedError

    def show_detail(self, connection: sqlite3.Connection, server: str, key: object | None) -> None:
        """Fill the detail panel for a selected row (None clears it); implemented by each page."""
        raise NotImplementedError

    def render(self, snapshot: SessionSnapshot) -> None:
        """Called by the window every refresh: reads the database when the throttle allows it."""
        due = self._last_refresh is None or self._monotonic() - self._last_refresh >= REFRESH_SECONDS
        if due or self._context.session.server != self._server:
            self.refresh()

    def refresh(self) -> None:
        """Read the rows now; a failed read keeps the previous rows and says so."""
        self._last_refresh = self._monotonic()
        server = self._context.session.server
        if server != self._server:
            self._server, self._selected = server, None
        window = period_window(self.period_bar.selection(), self._clock())
        rows = self._read(lambda connection: self.load_rows(connection, server, window))
        if rows is None:
            self.notice.configure(text=READ_FAILED_NOTICE)
            return
        self._rows = rows
        self._show_rows()

    def _read(self, action: Callable[[sqlite3.Connection], object]) -> object | None:
        connection = open_view_connection(self._context.session.database_path)
        if connection is None:
            return None
        try:
            return action(connection)
        except sqlite3.Error as error:
            logger.warning("lecture de la base impossible (%s)", error)
            return None
        finally:
            connection.close()

    def _show_rows(self) -> None:
        text = self.search_entry.get().strip().casefold()
        shown = [row for row in self._rows if text in row.cells[self._name_column].casefold()]
        truncated = self.table.set_rows(shown)
        self.notice.configure(text=TRUNCATED_NOTICE if truncated else "")
        self._refresh_detail()

    def _selection_changed(self, key: object | None) -> None:
        self._selected = key
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        server = self._server or self._context.session.server
        self._read(lambda connection: self.show_detail(connection, server, self._selected))
