"""The Administration tab: keys are generated on this PC, revoking one is asked of the server."""

import logging
from collections.abc import Callable
from datetime import datetime
from tkinter import messagebox

import customtkinter

from opendofusdata.admin_client import RevokeResult, revoke_key
from opendofusdata.admin_keys import make_key, new_key_id
from opendofusdata.admin_registry import (
    MAX_LABEL_LENGTH, AdminRegistry, KeyEntry, LabelExistsError, clean_label, registry_path, utc_now,
)
from opendofusdata.admin_rows import AdminRows
from opendofusdata.admin_settings import AdminSettings
from opendofusdata.background import BackgroundTask, TaskSnapshot, TaskState
from opendofusdata.capture_session import SessionSnapshot
from opendofusdata.env_file import env_file_path
from opendofusdata.ui_theme import (
    CARD_COLOR, CORNER_RADIUS, ERROR_COLOR, MUTED_COLOR, PADDING, SUCCESS_COLOR, TITLE_SIZE, TRANSPARENT, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import make_button, make_label
from opendofusdata.window_context import WindowContext

logger = logging.getLogger(__name__)

TITLE = "Administration"
SUBTITLE = ("Génère une clé par joueur et révoque-la au besoin. "
            "Cet onglet n'existe que parce que ton .env contient le secret.")
ENTRY_PLACEHOLDER = "Pseudo du joueur"
GENERATE_LABEL = "Générer une clé"
COPY_NEW_LABEL = "Copier"
HIDE_LABEL = "Masquer"
NEW_KEY_TEXT = "Clé générée pour {label}. Donne-la lui en privé."
COPIED_TEXT = "Clé copiée."
BAD_LABEL_TEXT = f"Pseudo invalide (1 à {MAX_LABEL_LENGTH} caractères, sans retour à la ligne)."
LABEL_EXISTS_TEXT = "Ce pseudo a déjà une clé active."
SAVE_FAILED_TEXT = "Le registre n'a pas pu être enregistré (voir le fichier de log)."
REVOKING_TEXT = "Révocation en cours..."
BUSY_TEXT = "Une révocation est déjà en cours, attends qu'elle se termine."
CONFIRM_TITLE = "Révoquer la clé"
CONFIRM_TEXT = "Révoquer la clé de {label} ? Elle sera refusée par le serveur immédiatement."
Revoke = Callable[[str, str, str], RevokeResult]
Confirm = Callable[[str], bool]


class RevokeFailed(Exception):
    """The server did not revoke the key; the message is what the administrator reads."""


def ask_confirmation(text: str) -> bool:
    """Ask yes or no in a system dialog."""
    return bool(messagebox.askyesno(CONFIRM_TITLE, text))


class AdminPage:
    """Generate (local, no network), copy and revoke (server) keys; the list comes from the local registry."""

    def __init__(self, parent: customtkinter.CTkBaseClass, context: WindowContext, settings: AdminSettings,
                 revoke: Revoke = revoke_key, confirm: Confirm = ask_confirmation,
                 clock: Callable[[], datetime] = utc_now) -> None:
        self._settings, self._revoke, self._confirm = settings, revoke, confirm
        self._registry = AdminRegistry(registry_path(env_file_path(context.config_path)), clock)
        self._pending_key_id = ""
        self._shown_snapshot: TaskSnapshot | None = None
        self.task = BackgroundTask(self._run_revocation, (RevokeFailed,))
        self.frame = customtkinter.CTkFrame(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._build()
        self.refresh_rows()

    def _build(self) -> None:
        make_label(self.frame, TITLE, TITLE_SIZE, bold=True, anchor="w").pack(fill="x", padx=PADDING, pady=PADDING)
        self.message_label = make_label(self.frame, SUBTITLE, color=MUTED_COLOR, anchor="w", justify="left",
                                        wraplength=WRAP_LENGTH * 2)
        self.message_label.pack(fill="x", padx=PADDING)
        bar = customtkinter.CTkFrame(self.frame, fg_color=TRANSPARENT, corner_radius=0)
        bar.pack(fill="x", padx=PADDING, pady=PADDING)
        self.label_entry = customtkinter.CTkEntry(bar, placeholder_text=ENTRY_PLACEHOLDER)
        self.label_entry.pack(side="left", fill="x", expand=True, padx=(0, PADDING))
        self.generate_button = make_button(bar, GENERATE_LABEL, self.generate)
        self.generate_button.pack(side="left")
        self._build_new_key_panel()
        self._scroll = customtkinter.CTkScrollableFrame(self.frame, fg_color=TRANSPARENT)
        self._pack_scroll()
        self.rows = AdminRows(self._scroll, self.copy_key, self.revoke)
        self.rows.pack(fill="x")

    def _pack_scroll(self) -> None:
        self._scroll.pack(fill="both", expand=True, padx=PADDING, pady=PADDING)

    def _build_new_key_panel(self) -> None:
        self._new_key_panel = customtkinter.CTkFrame(self.frame, fg_color=CARD_COLOR, corner_radius=CORNER_RADIUS)
        self.new_key_label = make_label(self._new_key_panel, "", anchor="w", wraplength=WRAP_LENGTH * 2)
        self.new_key_label.pack(side="left", fill="x", expand=True, padx=PADDING, pady=PADDING)
        self.copy_new_button = make_button(self._new_key_panel, COPY_NEW_LABEL, self.copy_new_key, width=90)
        self.copy_new_button.pack(side="left", padx=PADDING)
        make_button(self._new_key_panel, HIDE_LABEL, self.hide_new_key, width=90).pack(side="left", padx=(0, PADDING))

    @property
    def visible_entries(self) -> list[KeyEntry]:
        """The entries currently listed."""
        return self.rows.entries

    def row_status(self, key_id: str) -> str:
        """The status text of one listed key."""
        return self.rows.status_of(key_id)

    def _say(self, text: str, color: str = MUTED_COLOR) -> None:
        self.message_label.configure(text=text, text_color=color)

    def refresh_rows(self) -> None:
        """Re-read the registry and redraw the list if it changed."""
        self.rows.set_entries(self._registry.entries())

    def generate(self) -> None:
        """Make a key for the label in the field: local only, no network."""
        label = clean_label(self.label_entry.get())
        if label is None:
            self._say(BAD_LABEL_TEXT, ERROR_COLOR)
            return
        key_id = new_key_id()
        if self._register(label, key_id):
            self._show_new_key(make_key(self._settings.secret, key_id), label)
            self.label_entry.delete(0, "end")
            self.refresh_rows()

    def _register(self, label: str, key_id: str) -> bool:
        try:
            self._registry.add(label, key_id)
        except LabelExistsError:
            self._say(LABEL_EXISTS_TEXT, ERROR_COLOR)
        except OSError as error:
            logger.warning("registre des clés non enregistré : %s", error)
            self._say(SAVE_FAILED_TEXT, ERROR_COLOR)
        else:
            return True
        return False

    def _show_new_key(self, key: str, label: str) -> None:
        self.new_key_label.configure(text=key)
        self._scroll.pack_forget()  # the panel goes above the list: pack it first, then the list again
        self._new_key_panel.pack(fill="x", padx=PADDING)
        self._pack_scroll()
        self._say(NEW_KEY_TEXT.format(label=label), SUCCESS_COLOR)

    def hide_new_key(self) -> None:
        """Hide the freshly generated key (it can always be copied again from its row)."""
        self.new_key_label.configure(text="")
        self._new_key_panel.pack_forget()

    def _copy(self, key: str) -> None:
        self.frame.clipboard_clear()
        self.frame.clipboard_append(key)
        self._say(COPIED_TEXT)

    def copy_new_key(self) -> None:
        """Copy the key shown in the green panel."""
        self._copy(str(self.new_key_label.cget("text")))

    def copy_key(self, key_id: str) -> None:
        """Copy the key of a listed row (recomputed from its identifier and the secret)."""
        self._copy(make_key(self._settings.secret, key_id))

    def revoke(self, key_id: str) -> None:
        """After confirmation, ask the server to revoke the key (in the background)."""
        if self.task.snapshot().state is TaskState.RUNNING:
            self._say(BUSY_TEXT, ERROR_COLOR)
            return
        entry = next((item for item in self.visible_entries if item.key_id == key_id), None)
        if entry is None or not self._confirm(CONFIRM_TEXT.format(label=entry.label)):
            return
        self._pending_key_id = key_id
        if self.task.start():
            self.render(None)

    def _run_revocation(self) -> str:
        key_id = self._pending_key_id  # read once: the same key is revoked on the server and marked locally
        result = self._revoke(self._settings.server_url, self._settings.secret, key_id)
        if not result.ok:
            raise RevokeFailed(result.message)
        self._registry.mark_revoked(key_id)
        return result.message

    def render(self, snapshot: SessionSnapshot | None) -> None:
        """Show the revocation outcome once, and keep the list in step with the registry."""
        task = self.task.snapshot()
        if task is not self._shown_snapshot:
            self._shown_snapshot = task
            self._show_task(task)
        self.refresh_rows()

    def _show_task(self, task: TaskSnapshot) -> None:
        if task.state is TaskState.RUNNING:
            self._say(REVOKING_TEXT)
        elif task.state is TaskState.DONE:
            self._say(task.message, SUCCESS_COLOR)
        elif task.state is TaskState.FAILED:
            self._say(task.message, ERROR_COLOR)
