"""One setting per row: title and description on the left, the control on the right, extra content below.

Rows are stacked in a panel and separated by a thin line, so a section reads as one list instead of a pile of
cards. Any frame can be the parent of a row (the page uses a panel, the tests a plain frame).
"""

import customtkinter

from opendofusdata.ui_theme import (
    CARD_COLOR, CORNER_RADIUS, DIVIDER_COLOR, MUTED_COLOR, PADDING, PANEL_BORDER_COLOR, ROW_TITLE_SIZE, ROW_WRAP,
    SMALL_PADDING, TRANSPARENT,
)
from opendofusdata.ui_widgets import make_label

DESCRIPTION_SIZE = 12


class SettingRow(customtkinter.CTkFrame):
    """Text on the left (`title_label`, `description_label`), controls on the right, `body` below both."""

    def __init__(self, parent: customtkinter.CTkBaseClass, title: str, description: str | None = None) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.title_label = make_label(self, title, ROW_TITLE_SIZE, bold=True, anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w", padx=(PADDING, SMALL_PADDING), pady=(PADDING, 0))
        self.description_label: customtkinter.CTkLabel | None = None
        if description is not None:
            self.description_label = make_label(self, description, DESCRIPTION_SIZE, color=MUTED_COLOR, anchor="w",
                                                justify="left", wraplength=ROW_WRAP)
            self.description_label.grid(row=1, column=0, sticky="w", padx=(PADDING, SMALL_PADDING))
        self.controls = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0, width=1, height=1)
        self.controls.grid(row=0, column=1, rowspan=2, sticky="e", padx=PADDING, pady=(PADDING, 0))
        self._body: customtkinter.CTkFrame | None = None
        customtkinter.CTkFrame(self, fg_color=TRANSPARENT, width=1, height=PADDING, corner_radius=0).grid(
            row=3, column=0, columnspan=2)  # space under the last content of the row

    @property
    def body(self) -> customtkinter.CTkFrame:
        """The area under the text and the controls, created on first use (entries, status lines)."""
        if self._body is None:
            self._body = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0, width=1, height=1)
            self._body.grid(row=2, column=0, columnspan=2, sticky="ew", padx=PADDING, pady=(SMALL_PADDING, 0))
        return self._body


def make_row(parent: customtkinter.CTkBaseClass, title: str, description: str | None = None) -> SettingRow:
    """A row packed at the bottom of `parent`, with a divider above it when it is not the first one."""
    if parent.pack_slaves():
        customtkinter.CTkFrame(parent, width=1, height=1, fg_color=DIVIDER_COLOR, corner_radius=0).pack(
            fill="x", padx=PADDING)
    row = SettingRow(parent, title, description)
    row.pack(fill="x")
    return row


def make_panel(parent: customtkinter.CTkBaseClass) -> customtkinter.CTkFrame:
    """The rounded panel that holds the rows of one section."""
    return customtkinter.CTkFrame(parent, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS, border_width=1,
                                  border_color=PANEL_BORDER_COLOR)

