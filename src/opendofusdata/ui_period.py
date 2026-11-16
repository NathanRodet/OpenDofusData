"""The period dropdown of a view, with a custom date range."""

import tkinter
from collections.abc import Callable

import customtkinter

from opendofusdata.time_filters import PERIOD_CUSTOM, PERIODS, PeriodSelection, next_period, parse_custom_range
from opendofusdata.ui_theme import ERROR_COLOR, MUTED_COLOR, PERIOD_MENU_WIDTH, SMALL_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label

BAD_DATE_MESSAGE = "Dates invalides (JJ/MM/AAAA, début avant fin)"
DATE_ENTRY_WIDTH = 110
APPLY_LABEL = "Appliquer"
DATE_PLACEHOLDER = "JJ/MM/AAAA"
PERIOD_LABEL = "Période"
CUSTOM_HINT = "Saisis deux dates puis clique sur Appliquer."


class PeriodBar(customtkinter.CTkFrame):
    """A dropdown of the periods; Personnalisé reveals two date entries."""

    def __init__(self, parent: tkinter.Misc, on_change: Callable[[], None],
                 selection: PeriodSelection = PeriodSelection()) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._on_change = on_change
        self._selection = selection
        row = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0)
        row.pack(side="top", anchor="w")
        make_label(row, PERIOD_LABEL, color=MUTED_COLOR).pack(side="left", padx=(0, SMALL_PADDING))
        self.menu = customtkinter.CTkOptionMenu(row, values=list(PERIODS), width=PERIOD_MENU_WIDTH,
                                                command=self.set_period)
        self.menu.set(selection.period)
        self.menu.pack(side="left")
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
        self.menu.set(period)
        if period == PERIOD_CUSTOM:
            self.message_label.configure(text=CUSTOM_HINT, text_color=MUTED_COLOR)
            self._custom_row.pack(side="top", anchor="w", pady=(SMALL_PADDING, 0))
            return
        self._custom_row.pack_forget()
        self._selection = PeriodSelection(period)
        self._on_change()

    def widen(self) -> bool:
        """Show the next period of the list (the menu follows); False when there is none."""
        following = next_period(self._selection.period)
        if following is None:
            return False
        self.menu.set(following)
        self._selection = PeriodSelection(following)
        return True

    def restore(self, selection: PeriodSelection) -> None:
        """Go back to a selection without asking for a new read (used after a widening found nothing)."""
        self.menu.set(selection.period)
        self._selection = selection

    def apply_custom(self) -> None:
        """Apply the typed dates, or keep the previous selection and say why not."""
        try:
            start, end = parse_custom_range(self.start_entry.get(), self.end_entry.get())
        except ValueError:
            self.message_label.configure(text=BAD_DATE_MESSAGE, text_color=ERROR_COLOR)
            return
        self.message_label.configure(text="")
        self._selection = PeriodSelection(PERIOD_CUSTOM, start, end)
        self._on_change()
