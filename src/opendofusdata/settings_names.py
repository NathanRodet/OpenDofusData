"""The reference data card of the Réglages page: one click downloads names, servers, recipes and effects."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import customtkinter

from opendofusdata.background import BackgroundTask, TaskState
from opendofusdata.names_fetch import NamesFetchError, Progress, TransientFetchError
from opendofusdata.names_progress import DownloadProgress
from opendofusdata.names_refresh import RefreshResult, loaded_item_count, reference_data_missing
from opendofusdata.settings_rows import make_row
from opendofusdata.ui_theme import COMPACT_BUTTON_HEIGHT, ERROR_COLOR, MUTED_COLOR
from opendofusdata.ui_widgets import make_button, make_label
from opendofusdata.window_context import WindowContext

TITLE = "Noms, recettes et effets"
NOTE = ("Téléchargé tout seul au premier lancement depuis api.dofusdb.fr (noms d'objets, serveurs, recettes de craft, "
        "effets de brisage; environ 1 000 requêtes, quelques minutes). Ce bouton le relance. Sans ces données, les "
        "logs affichent N/A et les pages Craft et Brisage restent vides.")
NONE_LOADED_TEXT = "Aucune donnée chargée : les logs affichent N/A."
LOADED_TEXT = "{count} objets chargés."
RUNNING_TEXT = "Téléchargement en cours..."
RUNNING_DETAIL_TEXT = "Téléchargement en cours : {detail}"
DONE_TEXT = "{items} objets, {servers} serveurs, {recipes} recettes et {effects} objets avec effets chargés."
BUTTON_TEXT = "Télécharger les données de référence"
REFERENCE_BUTTON_WIDTH = 250  # the label is longer than the compact width
BUSY_BUTTON_TEXT = "Téléchargement..."
SUMMARY_MISSING = "absentes"
SUMMARY_PARTIAL = "incomplètes"
SUMMARY_RUNNING = "téléchargement"
SUMMARY_FAILED = "échec"
SUMMARY_UP_TO_DATE = "à jour"
FAILURES = (NamesFetchError, TransientFetchError, sqlite3.Error, OSError)
Refresh = Callable[[str, Path, Progress], RefreshResult]


class NamesCard:
    """Status line and download button; the download runs in a background task."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, refresh: Refresh) -> None:
        self._context, self._refresh = context, refresh
        self._count = loaded_item_count(context.session.database_path)
        self._missing = reference_data_missing(context.session.database_path, context.data_directory)
        self._progress = DownloadProgress()
        self.task = BackgroundTask(self._download, FAILURES)
        row = make_row(parent, TITLE, NOTE)
        self.status_label = make_label(row.body, "", color=MUTED_COLOR, anchor="w", justify="left")
        self.status_label.pack(fill="x")
        self.button = make_button(row.controls, BUTTON_TEXT, self.task.start, REFERENCE_BUTTON_WIDTH,
                                  COMPACT_BUTTON_HEIGHT)
        self.button.pack()
        self.render()

    def start_if_missing(self) -> bool:
        """Start the download when names, recipes or effects were never loaded (the first launch); True if started."""
        started = self._missing and self.task.start()
        if started:
            self.render()
        return started

    def summary(self) -> str:
        """A few words for the side menu: absent, downloading, failed or up to date."""
        state = self.task.snapshot().state
        if state is TaskState.RUNNING:
            return f"{SUMMARY_RUNNING} {self._progress.pages()}".strip()
        if state is TaskState.FAILED:
            return SUMMARY_FAILED
        if not self._missing or state is TaskState.DONE:
            return SUMMARY_UP_TO_DATE
        return SUMMARY_PARTIAL if self._count else SUMMARY_MISSING

    def _download(self) -> str:
        self._progress.reset()
        result = self._refresh(self._context.session.database_path, self._context.data_directory,
                               self._progress.report)
        self._count = result.items
        self._context.use_item_names(self._context.session.database_path)
        self._context.reference_data_changed()
        return DONE_TEXT.format(items=result.items, servers=result.servers, recipes=result.recipes,
                                effects=result.effects)

    def _status_text(self) -> tuple[str, str]:
        snapshot = self.task.snapshot()
        if snapshot.state is TaskState.RUNNING:
            detail = self._progress.detail()
            return (RUNNING_DETAIL_TEXT.format(detail=detail) if detail else RUNNING_TEXT), MUTED_COLOR
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
