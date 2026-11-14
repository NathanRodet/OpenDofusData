"""A sortable data table (dark ttk Treeview) that keeps its selection when rows are replaced."""

import tkinter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from tkinter import ttk

import customtkinter

from opendofusdata.table_model import TableRow, limit_rows, sort_rows
from opendofusdata.ui_theme import (
    ACCENT_COLOR, BODY_SIZE, DOWN_COLOR, HEADER_COLOR, MUTED_COLOR, ROW_HEIGHT, SELECTED_COLOR, TABLE_COLOR,
    TEXT_COLOR, TRANSPARENT, UP_COLOR,
)

STYLE_NAME = "OpenDofus.Treeview"
TAG_UP = "up"
TAG_DOWN = "down"
ASCENDING_MARK = " ▲"
DESCENDING_MARK = " ▼"
SCROLLBAR_WIDTH = 14


@dataclass(frozen=True)
class Column:
    """A table column: its title, its starting width and whether it holds numbers (right aligned)."""

    title: str
    width: int
    numeric: bool = False


def _define_style(widget: tkinter.Misc) -> None:
    style = ttk.Style(widget)
    style.theme_use("clam")
    style.configure(STYLE_NAME, background=TABLE_COLOR, fieldbackground=TABLE_COLOR, foreground=TEXT_COLOR,
                    rowheight=ROW_HEIGHT, borderwidth=0, font=("Segoe UI", BODY_SIZE - 1))
    style.configure(f"{STYLE_NAME}.Heading", background=HEADER_COLOR, foreground=MUTED_COLOR, relief="flat",
                    font=("Segoe UI", BODY_SIZE - 2, "bold"))
    style.map(STYLE_NAME, background=[("selected", SELECTED_COLOR)], foreground=[("selected", TEXT_COLOR)])
    style.map(f"{STYLE_NAME}.Heading", background=[("active", SELECTED_COLOR)])


class DataTable(customtkinter.CTkFrame):
    """Rows of text with clickable headers; the page replaces the rows, the table re-applies the sort."""

    def __init__(self, parent: tkinter.Misc, columns: Sequence[Column], on_select: Callable[[object | None], None],
                 default_sort: tuple[int, bool]) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._columns = list(columns)
        self._on_select = on_select
        self._sort = default_sort
        self._source: list[TableRow] = []
        self._shown: list[TableRow] = []
        self._silent = False
        _define_style(self)
        self._tree = self._build_tree()
        self._refresh_headings()

    def _build_tree(self) -> ttk.Treeview:
        names = [str(index) for index in range(len(self._columns))]
        tree = ttk.Treeview(self, columns=names, show="headings", selectmode="browse", style=STYLE_NAME)
        for name, column in zip(names, self._columns):
            tree.column(name, width=column.width, minwidth=column.width // 2,
                        anchor="center", stretch=True)
        tree.tag_configure(TAG_UP, foreground=UP_COLOR)
        tree.tag_configure(TAG_DOWN, foreground=DOWN_COLOR)
        tree.bind("<<TreeviewSelect>>", self._selection_changed)
        scrollbar = customtkinter.CTkScrollbar(self, width=SCROLLBAR_WIDTH, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        return tree

    def _refresh_headings(self) -> None:
        sorted_column, descending = self._sort
        for index, column in enumerate(self._columns):
            mark = (DESCENDING_MARK if descending else ASCENDING_MARK) if index == sorted_column else ""
            self._tree.heading(str(index), text=column.title + mark, anchor="center",
                               command=lambda chosen=index: self._header_clicked(chosen))

    def _header_clicked(self, column: int) -> None:
        sorted_column, descending = self._sort
        self.sort_by(column, not descending if column == sorted_column else False)

    def _selection_changed(self, _event: object) -> None:
        if not self._silent:
            self._on_select(self.selected_key())

    def sort_by(self, column: int, descending: bool) -> None:
        """Sort by a column and redraw the rows."""
        self._sort = (column, descending)
        self._refresh_headings()
        self.set_rows(self._source)

    def clear_selection(self) -> None:
        """Unselect the row without telling the page."""
        self._silent = True
        try:
            self._tree.selection_set(())
        finally:
            self._silent = False

    def selected_key(self) -> object | None:
        """The key of the selected row, or None."""
        selection = self._tree.selection()
        return self._shown[int(selection[0])].key if selection else None

    def set_rows(self, rows: Sequence[TableRow]) -> bool:
        """Show the rows sorted by the current column; keep the selection; True when rows were left out."""
        self._source = list(rows)
        previous = self.selected_key()
        self._shown, truncated = limit_rows(sort_rows(self._source, *self._sort))
        self._silent = True
        try:
            self._tree.delete(*self._tree.get_children())
            self._insert_rows(previous)
        finally:
            self._silent = False
        if previous is not None and self.selected_key() is None:
            self._on_select(None)
        return truncated

    def _insert_rows(self, selected_key: object | None) -> None:
        for index, row in enumerate(self._shown):
            self._tree.insert("", "end", iid=str(index), values=row.cells, tags=(row.tag,) if row.tag else ())
            if selected_key is not None and row.key == selected_key and not self._tree.selection():
                self._tree.selection_set(str(index))
