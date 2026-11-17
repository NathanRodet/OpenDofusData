"""A history list for the detail panels: date on the left, what happened in the middle, the value on the right."""

import tkinter
from collections.abc import Sequence

import customtkinter

from opendofusdata.ui_theme import MUTED_COLOR, SMALL_PADDING, STAT_ROW_COLOR, TEXT_COLOR, TINY_PADDING
from opendofusdata.ui_widgets import make_label

HistoryRow = tuple[str, str, str]  # date, subject, value
EMPTY_TEXT = "Aucun relevé"
HISTORY_TEXT_SIZE = 12
SUBJECT_COLUMN_WEIGHT = 1


class HistoryList(customtkinter.CTkFrame):
    """Same card as the stat lists, so the history reads like the figures above it; rebuilt only when it changes."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=STAT_ROW_COLOR, corner_radius=SMALL_PADDING, width=1, height=1)
        self._shown: tuple[HistoryRow, ...] = ()
        self.grid_columnconfigure(1, weight=SUBJECT_COLUMN_WEIGHT)

    @property
    def rows(self) -> tuple[HistoryRow, ...]:
        """The rows currently shown."""
        return self._shown

    def set_rows(self, rows: Sequence[HistoryRow]) -> None:
        """Show these rows (an empty sequence shows a short notice)."""
        new_rows = tuple(rows)
        if new_rows == self._shown and self.winfo_children():
            return
        self._shown = new_rows
        for child in self.winfo_children():
            child.destroy()
        if not new_rows:
            make_label(self, EMPTY_TEXT, HISTORY_TEXT_SIZE, color=MUTED_COLOR, anchor="w").grid(
                row=0, column=0, columnspan=3, sticky="w", padx=SMALL_PADDING, pady=SMALL_PADDING)
        for index, (moment, subject, value) in enumerate(new_rows):
            self._add_row(index, moment, subject, value)

    def _add_row(self, index: int, moment: str, subject: str, value: str) -> None:
        cells = ((moment, MUTED_COLOR, False, "w"), (subject, TEXT_COLOR, False, "w"), (value, TEXT_COLOR, True, "e"))
        for column, (text, color, bold, side) in enumerate(cells):
            make_label(self, text, HISTORY_TEXT_SIZE, bold=bold, color=color, anchor=side).grid(
                row=index, column=column, sticky=side, padx=SMALL_PADDING, pady=TINY_PADDING)
