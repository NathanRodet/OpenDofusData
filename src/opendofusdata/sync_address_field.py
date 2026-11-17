"""The server address field of the Synchronisation card: what the player typed, and whether it is usable."""

import customtkinter

from opendofusdata.sync_server_url import display_address, origin_from_text
from opendofusdata.ui_theme import COMPACT_BUTTON_HEIGHT, SMALL_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label

LABEL = "Domaine du serveur"
PLACEHOLDER = "serveur.exemple.fr"
ADDRESS_WIDTH = 300


class AddressField:
    """A labelled entry above the key line; empty means 'use the .env or the built-in address'."""

    def __init__(self, parent: customtkinter.CTkFrame, current: str | None) -> None:
        line = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        line.pack(fill="x", pady=(0, SMALL_PADDING))
        make_label(line, LABEL, anchor="w").pack(side="left", padx=(0, SMALL_PADDING))
        self.entry = customtkinter.CTkEntry(line, width=ADDRESS_WIDTH, height=COMPACT_BUTTON_HEIGHT,
                                            placeholder_text=PLACEHOLDER)
        self.entry.pack(side="left")
        self.shown = display_address(current)  # what the field held when the card was built
        if self.shown:
            self.entry.insert(0, self.shown)

    def text(self) -> str:
        """What the player typed, without the surrounding blanks."""
        return self.entry.get().strip()

    def origin(self) -> str | None:
        """The typed domain as an https address, or None when it is empty or not a valid domain."""
        return origin_from_text(self.text())

    def changed(self) -> bool:
        """True when the player edited the address since the card was built."""
        return self.text() != self.shown
