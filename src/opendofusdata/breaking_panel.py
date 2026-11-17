"""The detail panel of the Brisage page: the object, then one tab at a time shown as a rune table."""

import tkinter

import customtkinter

from opendofusdata.breaking_detail_text import DetailTab
from opendofusdata.ui_rune_grid import RuneGrid
from opendofusdata.ui_theme import (
    CARD_COLOR, CORNER_RADIUS, MUTED_COLOR, PADDING, SMALL_PADDING, TITLE_SIZE, WIDE_DETAIL_WIDTH,
)
from opendofusdata.ui_widgets import make_label

NO_SELECTION_TEXT = "Sélectionne un objet pour voir ses brisages, puis un brisage pour en voir le détail."
PANEL_WRAP = WIDE_DETAIL_WIDTH - 7 * PADDING  # margins and scrollbar of the panel
NAME_ROW, INFO_ROW, TABS_ROW, NOTE_ROW, GRID_ROW, HINT_ROW = range(6)


class BreakingPanel(customtkinter.CTkScrollableFrame):
    """Name and summary, a tab bar, the note of the tab and its rune table; redrawn only when something changed."""

    def __init__(self, parent: tkinter.Misc) -> None:
        super().__init__(parent, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        self.grid_columnconfigure(0, weight=1)
        self.name_label = make_label(self, NO_SELECTION_TEXT, TITLE_SIZE, bold=True, anchor="w", justify="left",
                                     wraplength=PANEL_WRAP)
        self.info_label = make_label(self, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=PANEL_WRAP)
        self.tab_bar = customtkinter.CTkSegmentedButton(self, values=[" "], command=self._title_chosen)
        self.note_label = make_label(self, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=PANEL_WRAP)
        self.rune_grid = RuneGrid(self)
        self.hint_label = make_label(self, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=PANEL_WRAP)
        self.name_label.grid(row=NAME_ROW, column=0, sticky="ew", padx=PADDING, pady=(PADDING, SMALL_PADDING))
        self.current_key: str | None = None
        self._tabs: dict[str, DetailTab] = {}
        self._titles: tuple[str, ...] = ()
        self._shown: tuple | None = None
        self.clear()

    @property
    def tab_keys(self) -> list[str]:
        """The keys of the tabs currently offered, in order."""
        return list(self._tabs)

    def clear(self, text: str = NO_SELECTION_TEXT) -> None:
        """Nothing selected: only the invitation to select something."""
        if self._shown == ("clear", text):
            return
        self._shown, self._tabs, self.current_key = ("clear", text), {}, None
        self.name_label.configure(text=text)
        for widget in (self.info_label, self.tab_bar, self.note_label, self.rune_grid, self.hint_label):
            widget.grid_remove()

    def show(self, name: str, info: str, tabs: list[DetailTab], hint: str = "", wanted: str | None = None) -> None:
        """Show the object and its tabs; `wanted` picks a tab (else the one already open, else the first)."""
        state = (name, info, tuple(tabs), hint, wanted)
        if self._shown == state:
            return
        self._shown = state
        self._tabs = {tab.key: tab for tab in tabs}
        if wanted in self._tabs:
            self.current_key = wanted
        elif self.current_key not in self._tabs:
            self.current_key = tabs[0].key
        self.name_label.configure(text=name)
        self._place(self.info_label, INFO_ROW, info, (0, SMALL_PADDING))
        self._place(self.hint_label, HINT_ROW, hint, (PADDING, PADDING))
        self._show_tabs()

    def _place(self, label: customtkinter.CTkLabel, row: int, text: str, pady: tuple[int, int]) -> None:
        label.configure(text=text)
        if text:
            label.grid(row=row, column=0, sticky="ew", padx=PADDING, pady=pady)
        else:
            label.grid_remove()

    def _show_tabs(self) -> None:
        titles = tuple(tab.title for tab in self._tabs.values())
        if titles != self._titles:
            self._titles = titles
            self.tab_bar.configure(values=list(titles))
        self.tab_bar.set(self._tabs[self.current_key].title)
        self.tab_bar.grid(row=TABS_ROW, column=0, sticky="w", padx=PADDING, pady=(SMALL_PADDING, SMALL_PADDING))
        self.rune_grid.grid(row=GRID_ROW, column=0, sticky="ew", padx=PADDING)
        self._show_current()

    def _show_current(self) -> None:
        tab = self._tabs[self.current_key]
        self._place(self.note_label, NOTE_ROW, tab.note, (0, SMALL_PADDING))
        self.rune_grid.set_tab(tab)

    def _title_chosen(self, title: str) -> None:
        for key, tab in self._tabs.items():
            if tab.title == title:
                self.current_key = key
                self._shown = None  # the next refresh redraws with the player's choice
                self._show_current()
                return
