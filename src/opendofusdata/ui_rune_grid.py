"""The rune table of a Brisage tab: a header, one line per rune (name, price, counts, value), then the totals."""

import tkinter

import customtkinter

from opendofusdata.breaking_detail_text import NO_COUNT, DetailTab, Entry, Total
from opendofusdata.ui_theme import DIVIDER_COLOR, DOWN_COLOR, MUTED_COLOR, SMALL_PADDING, STAT_ROW_COLOR, TEXT_COLOR, TINY_PADDING, UP_COLOR
from opendofusdata.ui_widgets import make_label
from opendofusdata.value_format import format_kamas

GRID_TEXT_SIZE = 12
NAME_WRAP = 150
NAME_HEADER, PRICE_HEADER, VALUE_HEADER = "Rune", "Prix", "Valeur"
EMPTY_TEXT = "Aucune rune"
LEFT, RIGHT = "w", "e"


def _kamas(value: float | None) -> str:
    return NO_COUNT if value is None else format_kamas(value)


def _total_color(total: Total) -> str:
    if total.positive is None:
        return TEXT_COLOR
    return UP_COLOR if total.positive else DOWN_COLOR


class RuneGrid(customtkinter.CTkFrame):
    """A tab shown as a real table: figures right-aligned in their own columns; rebuilt only when the tab changes."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=STAT_ROW_COLOR, corner_radius=SMALL_PADDING, width=1, height=1)
        self._shown: DetailTab | None = None
        self.grid_columnconfigure(0, weight=1)

    def set_tab(self, tab: DetailTab) -> None:
        """Show this tab (nothing is redrawn when it is the one already shown)."""
        if tab == self._shown and self.winfo_children():
            return
        self._shown = tab
        for child in self.winfo_children():
            child.destroy()
        columns = len(tab.headers) + 3  # name, price, the counts, value
        line = self._lines(tab)
        if not tab.entries:
            make_label(self, EMPTY_TEXT, GRID_TEXT_SIZE, color=MUTED_COLOR, anchor=LEFT).grid(
                row=line, column=0, columnspan=columns, sticky=LEFT, padx=SMALL_PADDING, pady=SMALL_PADDING)
            line += 1
        if tab.entries and tab.totals:
            customtkinter.CTkFrame(self, height=1, fg_color=DIVIDER_COLOR, corner_radius=0).grid(
                row=line, column=0, columnspan=columns, sticky="ew", padx=SMALL_PADDING, pady=SMALL_PADDING)
            line += 1
        self._totals(line, tab.totals, columns)

    def _lines(self, tab: DetailTab) -> int:
        """Draw the header and the rune lines; returns the first free row."""
        self._cells(0, (NAME_HEADER, PRICE_HEADER, *tab.headers, VALUE_HEADER), MUTED_COLOR, False)
        for index, entry in enumerate(tab.entries, start=1):
            self._cells(index, self._entry_texts(entry), TEXT_COLOR, False)
        return len(tab.entries) + 1

    def _cells(self, row: int, texts: tuple[str, ...], color: str, bold: bool) -> None:
        for column, text in enumerate(texts):
            side = LEFT if column == 0 else RIGHT
            make_label(self, text, GRID_TEXT_SIZE, bold=bold or column == len(texts) - 1 and row > 0, color=color,
                       anchor=side, justify="left", wraplength=NAME_WRAP if column == 0 else 0).grid(
                row=row, column=column, sticky=side, padx=SMALL_PADDING, pady=TINY_PADDING)

    @staticmethod
    def _entry_texts(entry: Entry) -> tuple[str, ...]:
        return (entry.name, _kamas(entry.price), *entry.counts, _kamas(entry.value))

    def _totals(self, first_row: int, totals: tuple[Total, ...], columns: int) -> None:
        for offset, total in enumerate(totals):
            make_label(self, total.label, GRID_TEXT_SIZE, color=MUTED_COLOR, anchor=LEFT).grid(
                row=first_row + offset, column=0, columnspan=columns - 1, sticky=LEFT, padx=SMALL_PADDING,
                pady=TINY_PADDING)
            make_label(self, total.text, GRID_TEXT_SIZE, bold=True, color=_total_color(total), anchor=RIGHT).grid(
                row=first_row + offset, column=columns - 1, sticky=RIGHT, padx=SMALL_PADDING, pady=TINY_PADDING)
