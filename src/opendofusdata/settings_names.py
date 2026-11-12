"""The "Noms d'objets" card of the Réglages page: one-click download of item names and servers."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import customtkinter

from opendofusdata.background import BackgroundTask, TaskState
from opendofusdata.item_labels import item_labeler_for_database, rates_for_database
from opendofusdata.names_fetch import NamesFetchError, TransientFetchError
from opendofusdata.names_refresh import RefreshResult, loaded_item_count
from opendofusdata.ui_theme import ERROR_COLOR, MUTED_COLOR, PADDING, TINY_PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import make_button, make_card, make_label
from opendofusdata.window_context import WindowContext

TITLE = "Noms d'objets"
NOTE = ("Facultatif. Télécharge les noms depuis api.dofusdb.fr (environ 430 requêtes, une seule fois) "
        "pour les afficher dans les logs.")
NONE_LOADED_TEXT = "Aucun nom chargé : les logs affichent N/A."
LOADED_TEXT = "{count} objets chargés."
RUNNING_TEXT = "Téléchargement en cours..."
DONE_TEXT = "{items} objets et {servers} serveurs chargés."
BUTTON_TEXT = "Télécharger les noms"
BUSY_BUTTON_TEXT = "Téléchargement..."
FAILURES = (NamesFetchError, TransientFetchError, sqlite3.Error, OSError)
Refresh = Callable[[str, Path], RefreshResult]


class NamesCard:
    """Status line and download button; the download runs in a background task."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, refresh: Refresh) -> None:
        self._context, self._refresh = context, refresh
        self._count = loaded_item_count(context.session.database_path)
        self.task = BackgroundTask(self._download, FAILURES)
        card = make_card(parent)
        make_label(card, TITLE, anchor="w").pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        self.status_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left",
                                       wraplength=WRAP_LENGTH)
        self.status_label.pack(fill="x", padx=PADDING)
        make_label(card, NOTE, color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", padx=PADDING, pady=TINY_PADDING)
        self.button = make_button(card, BUTTON_TEXT, self.task.start)
        self.button.pack(pady=PADDING)
        self.render()

    def _download(self) -> str:
        result = self._refresh(self._context.session.database_path, self._context.data_directory)
        self._count = result.items
        self._context.name_of = item_labeler_for_database(self._context.session.database_path)
        self._context.nuggets_of = rates_for_database(self._context.session.database_path)
        return DONE_TEXT.format(items=result.items, servers=result.servers)

    def _status_text(self) -> tuple[str, str]:
        snapshot = self.task.snapshot()
        if snapshot.state is TaskState.RUNNING:
            return RUNNING_TEXT, MUTED_COLOR
        if snapshot.state is TaskState.FAILED:
            return snapshot.message, ERROR_COLOR
        if snapshot.state is TaskState.DONE:
            return snapshot.message, MUTED_COLOR
        return (LOADED_TEXT.format(count=self._count) if self._count else NONE_LOADED_TEXT), MUTED_COLOR

    def render(self) -> None:
        """Refresh the status and the button from the task state."""
        text, color = self._status_text()
        self.status_label.configure(text=text, text_color=color)
        busy = self.task.snapshot().state is TaskState.RUNNING
        self.button.configure(state="disabled" if busy else "normal",
                              text=BUSY_BUTTON_TEXT if busy else BUTTON_TEXT)
