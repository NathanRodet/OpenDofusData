"""The Réglages page: cards for server, database, item names, price mode, updates and about."""

import logging
from collections.abc import Callable
from tkinter import filedialog

import customtkinter

from opendofusdata.app_config import load_config, save_config
from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.env_file import env_file_path
from opendofusdata.client_settings import (
    config_with_database, config_with_server, config_with_update_check, update_check_enabled,
)
from opendofusdata.names_refresh import refresh_reference_data
from opendofusdata.settings_about import AboutCard, UpdatesCard, open_url
from opendofusdata.settings_names import NamesCard, Refresh
from opendofusdata.settings_prices import PricesCard
from opendofusdata.settings_rows import make_row
from opendofusdata.settings_sections import SettingsSections
from opendofusdata.sync_server_url import configured_server_url
from opendofusdata.local_data_card import LocalDataCard
from opendofusdata.sync_interval_row import SyncIntervalRow
from opendofusdata.sync_settings_card import SyncSettingsCard
from opendofusdata.ui_theme import (
    ACCENT_COLOR, COMPACT_BUTTON_HEIGHT, COMPACT_BUTTON_WIDTH, ERROR_COLOR, MUTED_COLOR, PADDING, SWITCH_WIDTH,
    TITLE_SIZE, TRANSPARENT, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import make_button, make_label
from opendofusdata.window_context import WindowContext

logger = logging.getLogger(__name__)

TITLE = "Réglages"
SUBTITLE = "Un changement de serveur ou de base relance la capture."
SECTION_TITLES = ("Capture", "Données de référence", "Synchronisation", "Application")
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
                 refresh: Refresh = refresh_reference_data,
                 open_page: Callable[[str], None] = open_url) -> None:
        self._context, self._choose_database = context, choose_database
        self.frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        make_label(self.frame, TITLE, TITLE_SIZE, bold=True, anchor="w").pack(fill="x", padx=PADDING, pady=PADDING)
        self.message_label = make_label(self.frame, SUBTITLE, color=MUTED_COLOR, anchor="w", wraplength=WRAP_LENGTH)
        self.message_label.pack(fill="x", padx=PADDING)
        self._body = customtkinter.CTkScrollableFrame(self.frame, fg_color=TRANSPARENT)
        self._body.pack(fill="both", expand=True, padx=PADDING, pady=PADDING)
        self._sections = SettingsSections(self._body)
        self._build_cards(refresh, open_page)

    def _build_cards(self, refresh: Refresh, open_page: Callable[[str], None]) -> None:
        context = self._context
        capture = self._sections.add(SECTION_TITLES[0])
        self.server_menu = self._add_server_row(capture)
        self.database_label = self._add_database_card(capture)
        reference = self._sections.add(SECTION_TITLES[1])
        self.names_card = NamesCard(reference, context, refresh)
        self.prices_card = PricesCard(reference, context, self._save)
        synchronisation = self._sections.add(SECTION_TITLES[2])
        sync_address = configured_server_url(context.config_path, env_file_path(context.config_path))
        self.sync_card = SyncSettingsCard(synchronisation, context, server_url=sync_address, status=context.sync_status)
        self.interval_row = SyncIntervalRow(synchronisation, context)
        self.local_data_card = LocalDataCard(synchronisation, context)
        application = self._sections.add(SECTION_TITLES[3])
        self.update_switch = self._add_update_row(application)
        self.updates_card = UpdatesCard(application, context, open_page)
        self.about_card = AboutCard(application, open_page)

    @property
    def sections(self) -> list[tuple[str, customtkinter.CTkFrame]]:
        """The sections and their panels (for the layout tests)."""
        return self._sections.sections

    @property
    def section_headings(self) -> list:
        return self._sections.headings

    def _add_server_row(self, body: customtkinter.CTkFrame) -> customtkinter.CTkOptionMenu:
        current = self._context.session.server
        names = list(self._context.server_names)
        values = names if current in names else [current, *names]
        row = make_row(body, SERVER_LABEL)
        menu = customtkinter.CTkOptionMenu(row.controls, values=values, command=self.choose_server,
                                           fg_color=ACCENT_COLOR, width=COMPACT_BUTTON_WIDTH,
                                           height=COMPACT_BUTTON_HEIGHT)
        menu.set(current)
        menu.pack()
        return menu

    def _add_database_card(self, body: customtkinter.CTkFrame) -> customtkinter.CTkLabel:
        row = make_row(body, DATABASE_LABEL, self._context.session.database_path)
        make_button(row.controls, CHANGE_DATABASE_LABEL, self.change_database, COMPACT_BUTTON_WIDTH,
                    COMPACT_BUTTON_HEIGHT).pack()
        return row.description_label

    def _add_update_row(self, body: customtkinter.CTkFrame) -> customtkinter.CTkSwitch:
        row = make_row(body, UPDATE_LABEL)
        switch = customtkinter.CTkSwitch(row.controls, text="", width=SWITCH_WIDTH, progress_color=ACCENT_COLOR,
                                         command=self._update_toggled)
        switch.pack()
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
            self._context.use_item_names(path)
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
        """Refresh the names, synchronisation and updates cards (the other settings only change on user actions)."""
        self.names_card.render()
        self.sync_card.render()
        self.updates_card.render()
