"""The Réglages page: game server and database location, applied at the next capture start."""

import logging
from collections.abc import Callable
from tkinter import filedialog

import customtkinter

from opendofusdata.app_config import load_config, save_config
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.client_settings import config_with_database, config_with_server
from opendofusdata.item_labels import item_labeler_for_database
from opendofusdata.ui_theme import ACCENT_COLOR, ERROR_COLOR, MUTED_COLOR, PADDING, TINY_PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import add_title, make_button, make_card, make_label, make_page
from opendofusdata.window_context import WindowContext

logger = logging.getLogger(__name__)

TITLE = "Réglages"
SUBTITLE = "Ils s'appliquent au prochain démarrage de la capture."
SERVER_LABEL = "Serveur de jeu"
DATABASE_LABEL = "Base de données"
SAVED_MESSAGE = "Enregistré."
RESTART_MESSAGE = "Enregistré. Arrête puis relance la capture pour l'appliquer."
SAVE_FAILED_MESSAGE = "Ce réglage n'a pas pu être enregistré ({error})."
CHANGE_DATABASE_LABEL = "Changer l'emplacement"
DIALOG_TITLE = "Emplacement de la base de données"
DATABASE_EXTENSION = ".db"
DATABASE_FILE_TYPES = (("Base SQLite", "*" + DATABASE_EXTENSION), ("Tous les fichiers", "*.*"))
ChooseDatabase = Callable[[str], str | None]
ConfigUpdate = Callable[[dict[str, object], str], dict[str, object]]


def ask_database_path(current: str) -> str | None:
    """Ask for the database file with the system dialog; None when cancelled."""
    chosen = filedialog.asksaveasfilename(
        title=DIALOG_TITLE, initialfile=current, defaultextension=DATABASE_EXTENSION,
        filetypes=DATABASE_FILE_TYPES, confirmoverwrite=False)
    return chosen or None


class SettingsPage:
    """Game server menu and database path; every change is saved to config.json."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext,
                 choose_database: ChooseDatabase = ask_database_path) -> None:
        self._context, self._choose_database = context, choose_database
        self.frame, body = make_page(parent)
        add_title(body, TITLE, SUBTITLE)
        self.server_menu = self._add_server_row(body)
        card = make_card(body)
        make_label(card, DATABASE_LABEL, anchor="w").pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        self.database_label = make_label(card, context.session.database_path, color=MUTED_COLOR,
                                         anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.database_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))
        make_button(body, CHANGE_DATABASE_LABEL, self.change_database).pack(pady=PADDING)
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

    def choose_server(self, name: str) -> None:
        """Save the server and use it for the next capture."""
        session = self._context.session
        if self._save(config_with_server, name):
            session.apply_settings(session.database_path, name)

    def change_database(self) -> None:
        """Ask for a database file, save it and use it for the next capture."""
        session = self._context.session
        path = self._choose_database(session.database_path)
        if path and self._save(config_with_database, path):
            session.apply_settings(path, session.server)
            self.database_label.configure(text=path)
            self._context.name_of = item_labeler_for_database(path)

    def _save(self, update: ConfigUpdate, value: str) -> bool:
        path = self._context.config_path
        try:
            save_config(path, update(load_config(path), value))
        except OSError as error:
            logger.warning("réglage non enregistré : %s", error)
            self.message_label.configure(text=SAVE_FAILED_MESSAGE.format(error=error),
                                         text_color=ERROR_COLOR)
            return False
        self._show_saved()
        return True

    def _show_saved(self) -> None:
        busy = (CaptureStatus.RUNNING, CaptureStatus.STOPPING)
        running = self._context.session.snapshot().status in busy
        self.message_label.configure(text=RESTART_MESSAGE if running else SAVED_MESSAGE,
                                     text_color=MUTED_COLOR)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Nothing to refresh: the page only changes on user actions."""
