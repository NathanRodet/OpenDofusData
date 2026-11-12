"""The Réglages page: server, database, item names and update check."""

import logging
from collections.abc import Callable
from tkinter import filedialog

import customtkinter

from opendofusdata.app_config import load_config, save_config
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.client_settings import (
    config_with_database, config_with_server, config_with_update_check, update_check_enabled,
)
from opendofusdata.item_labels import item_labeler_for_database, rates_for_database
from opendofusdata.names_refresh import refresh_reference_data
from opendofusdata.settings_names import NamesCard, Refresh
from opendofusdata.ui_theme import (
    ACCENT_COLOR, ERROR_COLOR, MUTED_COLOR, PADDING, SWITCH_WIDTH, TINY_PADDING, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import add_title, make_button, make_card, make_label, make_page
from opendofusdata.window_context import WindowContext

logger = logging.getLogger(__name__)

TITLE = "Réglages"
SUBTITLE = "Un changement de serveur ou de base relance la capture."
SERVER_LABEL = "Serveur de jeu"
DATABASE_LABEL = "Base de données"
UPDATE_LABEL = "Vérifier les mises à jour au démarrage"
SAVED_MESSAGE = "Enregistré."
RESTARTED_MESSAGE = "Enregistré. La capture redémarre avec ce réglage."
SAVE_FAILED_MESSAGE = "Ce réglage n'a pas pu être enregistré ({error})."
CHANGE_DATABASE_LABEL = "Changer l'emplacement"
DIALOG_TITLE = "Emplacement de la base de données"
DATABASE_EXTENSION = ".db"
DATABASE_FILE_TYPES = (("Base SQLite", "*" + DATABASE_EXTENSION), ("Tous les fichiers", "*.*"))
ChooseDatabase = Callable[[str], str | None]
ConfigUpdate = Callable[[dict[str, object], object], dict[str, object]]


def ask_database_path(current: str) -> str | None:
    """Ask for the database file with the system dialog; None when cancelled."""
    chosen = filedialog.asksaveasfilename(
        title=DIALOG_TITLE, initialfile=current, defaultextension=DATABASE_EXTENSION,
        filetypes=DATABASE_FILE_TYPES, confirmoverwrite=False)
    return chosen or None


class SettingsPage:
    """Every change is saved to config.json; a running capture restarts to use it."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext,
                 choose_database: ChooseDatabase = ask_database_path,
                 refresh: Refresh = refresh_reference_data) -> None:
        self._context, self._choose_database = context, choose_database
        self.frame, body = make_page(parent, scrollable=True)
        add_title(body, TITLE, SUBTITLE)
        self.server_menu = self._add_server_row(body)
        self.database_label = self._add_database_card(body)
        self.names_card = NamesCard(body, context, refresh)
        self.update_switch = self._add_update_row(body)
        self.message_label = make_label(body, "", color=MUTED_COLOR, wraplength=WRAP_LENGTH)
        self.message_label.pack()

    def _add_server_row(self, body: customtkinter.CTkFrame) -> customtkinter.CTkOptionMenu:
        current = self._context.session.server
        names = list(self._context.server_names)
        values = names if current in names else [current, *names]
        card = make_card(body)
        make_label(card, SERVER_LABEL, anchor="w").pack(side="left", padx=PADDING, pady=PADDING)
        menu = customtkinter.CTkOptionMenu(card, values=values, command=self.choose_server,
                                           fg_color=ACCENT_COLOR)
        menu.set(current)
        menu.pack(side="right", padx=PADDING)
        return menu

    def _add_database_card(self, body: customtkinter.CTkFrame) -> customtkinter.CTkLabel:
        card = make_card(body)
        make_label(card, DATABASE_LABEL, anchor="w").pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        label = make_label(card, self._context.session.database_path, color=MUTED_COLOR, anchor="w",
                           justify="left", wraplength=WRAP_LENGTH)
        label.pack(fill="x", padx=PADDING)
        make_button(card, CHANGE_DATABASE_LABEL, self.change_database).pack(pady=PADDING)
        return label

    def _add_update_row(self, body: customtkinter.CTkFrame) -> customtkinter.CTkSwitch:
        card = make_card(body)
        make_label(card, UPDATE_LABEL, anchor="w").pack(side="left", padx=PADDING, pady=PADDING)
        switch = customtkinter.CTkSwitch(card, text="", width=SWITCH_WIDTH, progress_color=ACCENT_COLOR,
                                         command=self._update_toggled)
        switch.pack(side="right", padx=PADDING)
        if update_check_enabled(load_config(self._context.config_path)):
            switch.select()
        self._context.updates.enabled = bool(switch.get())
        return switch

    def _update_toggled(self) -> None:
        enabled = bool(self.update_switch.get())
        self._context.updates.enabled = enabled
        if self._save(config_with_update_check, enabled):
            self.message_label.configure(text=SAVED_MESSAGE, text_color=MUTED_COLOR)

    def choose_server(self, name: str) -> None:
        """Save the server and restart the capture with it."""
        session = self._context.session
        if self._save(config_with_server, name):
            session.apply_settings(session.database_path, name)
            self._applied()

    def change_database(self) -> None:
        """Ask for a database file, save it and restart the capture with it."""
        session = self._context.session
        path = self._choose_database(session.database_path)
        if path and self._save(config_with_database, path):
            session.apply_settings(path, session.server)
            self.database_label.configure(text=path)
            self._context.name_of = item_labeler_for_database(path)
            self._context.nuggets_of = rates_for_database(path)
            self._applied()

    def _save(self, update: ConfigUpdate, value: object) -> bool:
        path = self._context.config_path
        try:
            save_config(path, update(load_config(path), value))
        except OSError as error:
            logger.warning("réglage non enregistré : %s", error)
            self.message_label.configure(text=SAVE_FAILED_MESSAGE.format(error=error),
                                         text_color=ERROR_COLOR)
            return False
        return True

    def _applied(self) -> None:
        running = self._context.session.snapshot().status in (CaptureStatus.RUNNING, CaptureStatus.STOPPING)
        if running:
            self._context.restart_capture()
        self.message_label.configure(text=RESTARTED_MESSAGE if running else SAVED_MESSAGE,
                                     text_color=MUTED_COLOR)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Refresh the item-names card (the other settings only change on user actions)."""
        self.names_card.render()
