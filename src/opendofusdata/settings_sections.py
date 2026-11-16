"""Titled sections of the Réglages page: a heading and a panel of rows, in one left-aligned column."""

import customtkinter

from opendofusdata.settings_rows import make_panel
from opendofusdata.ui_theme import COLUMN_WIDTH, PADDING, SECTION_TITLE_SIZE, TEXT_COLOR, TINY_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label


class SettingsSections:
    """Each section is a heading above a panel; every panel has the width of the column."""

    def __init__(self, body: customtkinter.CTkBaseClass) -> None:
        self.content = customtkinter.CTkFrame(body, fg_color=TRANSPARENT, corner_radius=0)
        self.content.pack(anchor="nw")
        self.content.grid_columnconfigure(0, minsize=COLUMN_WIDTH, weight=0)  # fixed column, whatever the window
        self._next_row = 0
        self.headings: list[customtkinter.CTkLabel] = []
        self.sections: list[tuple[str, customtkinter.CTkFrame]] = []

    def add(self, title: str) -> customtkinter.CTkFrame:
        """Start a section; the returned panel is the parent of its rows."""
        heading = make_label(self.content, title, SECTION_TITLE_SIZE, bold=True, color=TEXT_COLOR, anchor="w")
        heading.grid(row=self._next_row, column=0, sticky="ew", padx=TINY_PADDING, pady=(PADDING, TINY_PADDING))
        panel = make_panel(self.content)
        panel.grid(row=self._next_row + 1, column=0, sticky="ew")
        self._next_row += 2
        self.headings.append(heading)
        self.sections.append((title, panel))
        return panel
