"""The "Données locales" card of the Réglages page: optional purge of readings older than seven days."""

import sqlite3
from collections.abc import Callable
from tkinter import messagebox

import customtkinter

from opendofusdata.app_config import load_config, save_config
from opendofusdata.background import BackgroundTask, TaskSnapshot, TaskState
from opendofusdata.local_purge import LOCAL_RETENTION_DAYS, PurgeResult, purge_database_file
from opendofusdata.purge_options import config_with_purge, purge_enabled
from opendofusdata.ui_theme import ERROR_COLOR, MUTED_COLOR, PADDING, SUCCESS_COLOR, TINY_PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import make_button, make_card, make_card_title, make_label
from opendofusdata.window_context import WindowContext

TITLE = "Données locales"
NOTE = (f"Supprime de ta base les prix et statistiques de plus de {LOCAL_RETENTION_DAYS} jours, en gardant toujours "
        "le dernier prix connu de chaque objet. Tes favoris, tes observations de familiers, les noms d'objets, "
        "les brisages et les améliorations de familiers ne sont jamais touchés.")
AUTO_LABEL = "Purge automatique au lancement"
PURGE_LABEL = "Purger maintenant"
PURGING_LABEL = "Purge en cours..."
CONFIRM_TITLE = "Purger les anciens relevés"
CONFIRM_TEXT = (f"Supprimer les relevés de plus de {LOCAL_RETENTION_DAYS} jours de la base ? Le dernier prix connu "
                "de chaque objet, tes favoris et tes autres données sont gardés. Cette action est définitive.")
DONE_TEXT = "{count} ligne(s) supprimée(s)."
NOTHING_TEXT = "Rien à supprimer."
SAVE_FAILED_TEXT = "Le réglage n'a pas pu être enregistré (voir le fichier de log)."
Purge = Callable[[str], PurgeResult]
Confirm = Callable[[str], bool]


class PurgeFailed(Exception):
    """The purge could not run; the message is what the player reads."""


def ask_confirmation(text: str) -> bool:
    """Ask yes or no in a system dialog."""
    return bool(messagebox.askyesno(CONFIRM_TITLE, text))


class LocalDataCard:
    """The automatic purge box (off by default) and a purge now button that runs in the background."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, purge: Purge = purge_database_file,
                 confirm: Confirm = ask_confirmation) -> None:
        self._context, self._purge, self._confirm = context, purge, confirm
        self._shown_snapshot: TaskSnapshot | None = None
        self.task = BackgroundTask(self._run_purge, (PurgeFailed,))
        self._build(make_card(parent))
        self.render()

    def _build(self, card: customtkinter.CTkFrame) -> None:
        make_card_title(card, TITLE).pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        make_label(card, NOTE, color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", padx=PADDING)
        self.auto_box = customtkinter.CTkCheckBox(card, text=AUTO_LABEL, command=self.toggle_auto)
        self.auto_box.pack(anchor="w", padx=PADDING, pady=PADDING)
        (self.auto_box.select if purge_enabled(load_config(self._context.config_path)) else self.auto_box.deselect)()
        self.purge_button = make_button(card, PURGE_LABEL, self.purge_now)
        self.purge_button.pack(pady=(0, TINY_PADDING))
        self.status_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.status_label.pack(fill="x", padx=PADDING, pady=PADDING)

    def toggle_auto(self) -> None:
        """Save the automatic purge setting, following the check box."""
        path = self._context.config_path
        try:
            save_config(path, config_with_purge(load_config(path), bool(self.auto_box.get())))
        except OSError:
            self.status_label.configure(text=SAVE_FAILED_TEXT, text_color=ERROR_COLOR)

    def purge_now(self) -> None:
        """After confirmation, purge the current database in the background."""
        if self._confirm(CONFIRM_TEXT) and self.task.start():
            self.render()

    def _run_purge(self) -> str:
        try:
            result = self._purge(self._context.session.database_path)
        except (sqlite3.Error, OSError) as error:  # a locked or missing database is reported to the player
            raise PurgeFailed(f"La purge a échoué: {error}") from None
        total = result.lot_prices + result.market_stats
        return DONE_TEXT.format(count=total) if total else NOTHING_TEXT

    def render(self) -> None:
        """Show the purge outcome once and keep the button in step with the task."""
        snapshot = self.task.snapshot()
        running = snapshot.state is TaskState.RUNNING
        if snapshot is not self._shown_snapshot:
            self._shown_snapshot = snapshot
            self._show_snapshot(snapshot)
        self.purge_button.configure(state="disabled" if running else "normal",
                                    text=PURGING_LABEL if running else PURGE_LABEL)

    def _show_snapshot(self, snapshot: TaskSnapshot) -> None:
        colors = {TaskState.RUNNING: MUTED_COLOR, TaskState.DONE: SUCCESS_COLOR, TaskState.FAILED: ERROR_COLOR}
        if snapshot.state in colors:
            text = PURGING_LABEL if snapshot.state is TaskState.RUNNING else snapshot.message
            self.status_label.configure(text=text, text_color=colors[snapshot.state])
