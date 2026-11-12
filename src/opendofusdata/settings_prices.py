"""The "Prix utilisé pour les estimations" card of the Réglages page."""

from collections.abc import Callable

import customtkinter

from opendofusdata.app_config import load_config
from opendofusdata.client_settings import config_with_price_mode, price_mode_from_config
from opendofusdata.price_rules import PRICE_MODE_LABELS
from opendofusdata.ui_theme import ACCENT_COLOR, MUTED_COLOR, PADDING, TINY_PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import make_card, make_label
from opendofusdata.window_context import WindowContext

TITLE = "Prix utilisé pour les estimations"
NOTE = "Sert au brisage (valeur des runes) et aux familiers (prix d'une ressource)."
Save = Callable[[Callable[[dict[str, object], object], dict[str, object]], object], bool]


class PricesCard:
    """A menu of the three price modes; the choice is saved to the config."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, save: Save) -> None:
        self._save = save
        card = make_card(parent)
        make_label(card, TITLE, anchor="w").pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        make_label(card, NOTE, color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", padx=PADDING)
        self.menu = customtkinter.CTkOptionMenu(card, values=list(PRICE_MODE_LABELS.values()),
                                                command=self.choose, fg_color=ACCENT_COLOR)
        self.menu.set(PRICE_MODE_LABELS[price_mode_from_config(load_config(context.config_path))])
        self.menu.pack(pady=PADDING)

    def choose(self, label: str) -> None:
        """Save the mode whose label was chosen."""
        for mode, mode_label in PRICE_MODE_LABELS.items():
            if mode_label == label:
                self._save(config_with_price_mode, mode)
