"""Titled sections of cards laid out in equal columns (the structure of the Réglages page)."""

import customtkinter

from opendofusdata.ui_theme import CARD_MIN_WIDTH, MUTED_COLOR, PADDING, TINY_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label

MAX_COLUMNS = 2
CARD_GAP = 6
HEADING_SIZE = 13


class SettingsSections:
    """Each section is a heading and a grid of cards; all the cards of a section share the column width."""

    def __init__(self, body: customtkinter.CTkBaseClass) -> None:
        self._body = body
        self._grids: list[tuple[str, customtkinter.CTkFrame]] = []
        self.headings: list[customtkinter.CTkLabel] = []
        self.sections: list[tuple[str, list[customtkinter.CTkBaseClass]]] = []
        self._columns = 0

    def add(self, title: str) -> customtkinter.CTkFrame:
        """Start a section; the returned frame is the parent of the cards of that section."""
        heading = make_label(self._body, title, HEADING_SIZE, bold=True, color=MUTED_COLOR, anchor="w")
        heading.pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        grid = customtkinter.CTkFrame(self._body, fg_color=TRANSPARENT, corner_radius=0)
        grid.pack(fill="x")
        self.headings.append(heading)
        self._grids.append((title, grid))
        return grid

    def collect(self) -> None:
        """Remember the cards created in each section (they were packed into it) and lay them out."""
        self.sections = [(title, grid.pack_slaves()) for title, grid in self._grids]
        self._columns = 0
        self.reflow(CARD_MIN_WIDTH)

    def reflow(self, width: int) -> None:
        """As many columns of at least CARD_MIN_WIDTH as fit, at most MAX_COLUMNS."""
        columns = min(MAX_COLUMNS, max(1, width // CARD_MIN_WIDTH))
        if columns == self._columns:
            return
        self._columns = columns
        for (_, grid), (_, cards) in zip(self._grids, self.sections):
            for index in range(MAX_COLUMNS):
                used = index < columns
                grid.grid_columnconfigure(index, weight=1 if used else 0, uniform="cards" if used else "")
            for card in cards:
                card.pack_forget()
            for index, card in enumerate(cards):
                card.grid(row=index // columns, column=index % columns, sticky="nsew", padx=CARD_GAP, pady=CARD_GAP)
