"""The server address field of the Synchronisation card: what the player typed, and whether it is usable."""

import customtkinter

from opendofusdata.env_file import canonical_origin
from opendofusdata.ui_theme import COMPACT_BUTTON_HEIGHT, SMALL_PADDING, TRANSPARENT
from opendofusdata.ui_widgets import make_label

LABEL = "Adresse du serveur"
PLACEHOLDER = "https://serveur.exemple.fr"
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
        self.shown = current or ""  # what the field held when the card was built
        if current:
            self.entry.insert(0, current)

    def text(self) -> str:
        """What the player typed, without the surrounding blanks."""
        return self.entry.get().strip()

    def origin(self) -> str | None:
        """The typed address in canonical form, or None when it is empty or not an https address."""
        text = self.text()
        return canonical_origin(text) if text else None

    def changed(self) -> bool:
        """True when the player edited the address since the card was built."""
        return self.text() != self.shown
