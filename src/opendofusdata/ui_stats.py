"""A list of labelled values (muted label on the left, bold value on the right) for the detail cards."""

import tkinter
from collections.abc import Sequence

import customtkinter

from opendofusdata.ui_theme import MUTED_COLOR, SMALL_PADDING, STAT_ROW_COLOR, TEXT_COLOR, TINY_PADDING
from opendofusdata.ui_widgets import make_label

StatRow = tuple[str, str, str | None]  # label, value, optional value colour
VALUE_COLUMN_WEIGHT = 1


class StatList(customtkinter.CTkFrame):
    """Rows of label / value; rebuilt only when the content changes."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=STAT_ROW_COLOR, corner_radius=SMALL_PADDING)
        self._shown: tuple[StatRow, ...] = ()
        self.grid_columnconfigure(1, weight=VALUE_COLUMN_WEIGHT)

    @property
    def rows(self) -> tuple[StatRow, ...]:
        """The rows currently shown."""
        return self._shown

    def set_rows(self, rows: Sequence[StatRow]) -> None:
        """Show these rows (an empty sequence empties the list)."""
        new_rows = tuple(rows)
        if new_rows == self._shown:
            return
        self._shown = new_rows
        for child in self.winfo_children():
            child.destroy()
        for index, (label, value, color) in enumerate(new_rows):
            make_label(self, label, color=MUTED_COLOR, anchor="w").grid(
                row=index, column=0, sticky="w", padx=SMALL_PADDING, pady=TINY_PADDING)
            make_label(self, value, bold=True, color=color or TEXT_COLOR, anchor="e").grid(
                row=index, column=1, sticky="e", padx=SMALL_PADDING, pady=TINY_PADDING)
