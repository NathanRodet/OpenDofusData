"""The period buttons of a view, with a custom date range."""

import tkinter
from collections.abc import Callable

import customtkinter

from opendofusdata.time_filters import PERIOD_CUSTOM, PERIODS, PeriodSelection, parse_custom_range
from opendofusdata.ui_theme import ERROR_COLOR, MUTED_COLOR, SMALL_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label

BAD_DATE_MESSAGE = "Dates invalides (JJ/MM/AAAA, début avant fin)"
DATE_ENTRY_WIDTH = 110
APPLY_LABEL = "Appliquer"
DATE_PLACEHOLDER = "JJ/MM/AAAA"


class PeriodBar(customtkinter.CTkFrame):
    """Seven segmented buttons; Personnalisé reveals two date entries."""

    def __init__(self, parent: tkinter.Misc, on_change: Callable[[], None],
                 selection: PeriodSelection = PeriodSelection()) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._on_change = on_change
        self._selection = selection
        self._buttons = customtkinter.CTkSegmentedButton(self, values=list(PERIODS), command=self.set_period)
        self._buttons.set(selection.period)
        self._buttons.pack(side="top", anchor="w")
        self._custom_row = customtkinter.CTkFrame(self, fg_color=TRANSPARENT)
        self.start_entry = self._add_entry()
        self.end_entry = self._add_entry()
        customtkinter.CTkButton(self._custom_row, text=APPLY_LABEL, width=DATE_ENTRY_WIDTH,
                                command=self.apply_custom).pack(side="left", padx=SMALL_PADDING)
        self.message_label = make_label(self._custom_row, "", color=ERROR_COLOR)
        self.message_label.pack(side="left")

    def _add_entry(self) -> customtkinter.CTkEntry:
        entry = customtkinter.CTkEntry(self._custom_row, width=DATE_ENTRY_WIDTH, placeholder_text=DATE_PLACEHOLDER,
                                       placeholder_text_color=MUTED_COLOR)
        entry.pack(side="left", padx=(0, SMALL_PADDING))
        return entry

    def selection(self) -> PeriodSelection:
        """The selection currently applied."""
        return self._selection

    def set_period(self, period: str) -> None:
        """Choose a period; Personnalisé waits for valid dates before it is applied."""
        self._buttons.set(period)
        if period == PERIOD_CUSTOM:
            self._custom_row.pack(side="top", anchor="w", pady=(SMALL_PADDING, 0))
            return
        self._custom_row.pack_forget()
        self._selection = PeriodSelection(period)
        self._on_change()

    def apply_custom(self) -> None:
        """Apply the typed dates, or keep the previous selection and say why not."""
        try:
            start, end = parse_custom_range(self.start_entry.get(), self.end_entry.get())
        except ValueError:
            self.message_label.configure(text=BAD_DATE_MESSAGE)
            return
        self.message_label.configure(text="")
        self._selection = PeriodSelection(PERIOD_CUSTOM, start, end)
        self._on_change()
