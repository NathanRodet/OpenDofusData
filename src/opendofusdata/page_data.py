"""The Données page: one switch per data category, with its record counter."""

import logging
from dataclasses import dataclass

import customtkinter

from opendofusdata.app_config import load_config, save_config
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.categories import (
    CATEGORIES, CATEGORY_BREAKING, CATEGORY_HDV, CATEGORY_PETS, CATEGORY_RECYCLING, DataCategory,
    config_with_categories,
)
from opendofusdata.ui_theme import (
    ACCENT_COLOR, ERROR_COLOR, MUTED_COLOR, PADDING, SMALL_PADDING, SWITCH_WIDTH, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import add_title, make_card, make_label, make_page
from opendofusdata.window_context import WindowContext
from opendofusdata.window_format import records_text, total_records

logger = logging.getLogger(__name__)

TITLE = "Ce que l'outil collecte"
SUBTITLE = "Chaque catégorie s'active ou se désactive."
SOON_TEXT = "bientôt"
PETS_RECONNECT_TEXT = "reconnecte-toi au jeu"
SAVE_FAILED_MESSAGE = "Ce choix n'a pas pu être enregistré ({error}). Il reste actif jusqu'à la fermeture."


@dataclass
class CategoryRow:
    """The widgets of one category line."""

    switch: customtkinter.CTkSwitch
    count_label: customtkinter.CTkLabel


class DataPage:
    """Lists the four categories; only available ones can be toggled."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext) -> None:
        self._context = context
        self.frame, body = make_page(parent)
        add_title(body, TITLE, SUBTITLE)
        self.rows = {category.key: self._add_row(body, category) for category in CATEGORIES}
        self.message_label = make_label(body, "", color=ERROR_COLOR, anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.message_label.pack(fill="x", pady=SMALL_PADDING)

    def _add_row(self, body: customtkinter.CTkFrame, category: DataCategory) -> CategoryRow:
        card = make_card(body)
        make_label(card, category.label, anchor="w").pack(side="left", padx=PADDING, pady=PADDING)
        switch = customtkinter.CTkSwitch(card, text="", width=SWITCH_WIDTH, progress_color=ACCENT_COLOR,
                                         command=lambda: self._toggled(category.key))
        switch.pack(side="right", padx=PADDING)
        count_label = make_label(card, records_text(0) if category.available else SOON_TEXT,
                                 color=MUTED_COLOR)
        count_label.pack(side="right", padx=PADDING)
        self._initialise_switch(switch, category)
        return CategoryRow(switch, count_label)

    def _initialise_switch(self, switch: customtkinter.CTkSwitch, category: DataCategory) -> None:
        if self._context.session.categories.is_enabled(category.key):
            switch.select()
        if not category.available:
            switch.configure(state="disabled")

    def _toggled(self, key: str) -> None:
        settings = self._context.session.categories
        settings.set_enabled(key, bool(self.rows[key].switch.get()))
        try:
            config = load_config(self._context.config_path)
            save_config(self._context.config_path, config_with_categories(config, settings))
        except OSError as error:
            logger.warning("catégories non enregistrées : %s", error)
            self.message_label.configure(text=SAVE_FAILED_MESSAGE.format(error=error))
            return
        self.message_label.configure(text="")

    def _pets_text(self, snapshot: SessionSnapshot) -> str:
        """The pet counter, or the way out while the inventory of this connection has not been seen."""
        waiting = (self._context.session.categories.is_enabled(CATEGORY_PETS)
                   and snapshot.status is CaptureStatus.RUNNING and not snapshot.pets_inventory_seen)
        return PETS_RECONNECT_TEXT if waiting else records_text(snapshot.pet_count)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Refresh the counters of the categories that have a decoder."""
        self.rows[CATEGORY_HDV].count_label.configure(text=records_text(total_records(snapshot)))
        self.rows[CATEGORY_RECYCLING].count_label.configure(text=records_text(snapshot.recycling_count))
        self.rows[CATEGORY_PETS].count_label.configure(text=self._pets_text(snapshot))
        self.rows[CATEGORY_BREAKING].count_label.configure(text=records_text(snapshot.breaking_count))
