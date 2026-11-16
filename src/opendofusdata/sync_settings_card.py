"""The "Synchronisation" card of the Réglages page: the player's key and a connection test."""

from collections.abc import Callable

import customtkinter

from opendofusdata.background import BackgroundTask, TaskSnapshot, TaskState
from opendofusdata.sync_client import ConnectionResult, check_connection
from opendofusdata.sync_key import clean_key, key_format_ok, load_sync_key, save_sync_key
from opendofusdata.ui_theme import ERROR_COLOR, MUTED_COLOR, PADDING, SUCCESS_COLOR, TINY_PADDING, WRAP_LENGTH
from opendofusdata.ui_widgets import make_button, make_card, make_card_title, make_label
from opendofusdata.window_context import WindowContext

MASK_CHARACTER = "*"
ENTRY_WIDTH = 300
TITLE = "Synchronisation"
NOTE = ("Colle ici la clé donnée par l'administrateur. Le serveur de synchronisation arrive plus tard: "
        "pour l'instant, le seul envoi est le test de connexion, quand tu cliques dessus (il n'envoie que ta clé).")
SHOW_LABEL = "Afficher la clé"
SAVE_LABEL = "Enregistrer"
TEST_LABEL = "Tester la connexion"
TESTING_LABEL = "Test en cours..."
SAVED_TEXT = "Clé enregistrée."
REMOVED_TEXT = "Clé retirée."
SAVE_FAILED_TEXT = "La clé n'a pas pu être enregistrée (voir le fichier de log)."
MISSING_KEY_TEXT = "Colle d'abord ta clé."
BAD_FORMAT_TEXT = "Format de clé invalide (elle ressemble à odk1.xxxxxxxxxxx.yyyy...)."
NOT_CONFIGURED_TEXT = "Serveur de synchronisation non configuré."
Check = Callable[[str, str], ConnectionResult]


class SyncTestFailed(Exception):
    """The connection test did not succeed; the message is what the player reads."""


class SyncSettingsCard:
    """Key field (masked), save button and connection test; nothing is sent until the test button is pressed."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, check: Check = check_connection,
                 server_url: str | None = None) -> None:
        self._config_path, self._check, self._server_url = context.config_path, check, server_url
        self._pending_key = ""
        self._shown_snapshot: TaskSnapshot | None = None
        self.task = BackgroundTask(self._run_test, (SyncTestFailed,))
        self._build(make_card(parent))
        self.render()

    def _build(self, card: customtkinter.CTkFrame) -> None:
        make_card_title(card, TITLE).pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        make_label(card, NOTE, color=MUTED_COLOR, anchor="w", justify="left",
                   wraplength=WRAP_LENGTH).pack(fill="x", padx=PADDING)
        self.entry = customtkinter.CTkEntry(card, show=MASK_CHARACTER, width=ENTRY_WIDTH)
        self.entry.pack(padx=PADDING, pady=(PADDING, TINY_PADDING))
        saved_key = load_sync_key(self._config_path)
        if saved_key:
            self.entry.insert(0, saved_key)
        self.show_box = customtkinter.CTkCheckBox(card, text=SHOW_LABEL, command=self.toggle_visibility)
        self.show_box.pack(padx=PADDING)
        self.save_button = make_button(card, SAVE_LABEL, self.save)
        self.save_button.pack(pady=(PADDING, TINY_PADDING))
        self.test_button = make_button(card, TEST_LABEL, self.test)
        self.test_button.pack()
        self.status_label = make_label(card, "", color=MUTED_COLOR, anchor="w", justify="left", wraplength=WRAP_LENGTH)
        self.status_label.pack(fill="x", padx=PADDING, pady=PADDING)
        if not self._server_url:
            self._set_status(NOT_CONFIGURED_TEXT, MUTED_COLOR)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, text_color=color)

    def toggle_visibility(self) -> None:
        """Show the key in clear or mask it, following the check box."""
        self.entry.configure(show="" if self.show_box.get() else MASK_CHARACTER)

    def save(self) -> None:
        """Save the key from the field (an empty field removes it); a malformed key is refused."""
        text = clean_key(self.entry.get())
        if text and not key_format_ok(text):
            self._set_status(BAD_FORMAT_TEXT, ERROR_COLOR)
        elif save_sync_key(self._config_path, text or None):
            self._set_status(SAVED_TEXT if text else REMOVED_TEXT, MUTED_COLOR)
        else:
            self._set_status(SAVE_FAILED_TEXT, ERROR_COLOR)

    def test(self) -> None:
        """Test the key currently in the field (saved or not) against the server, in the background."""
        text = clean_key(self.entry.get())
        if not text:
            self._set_status(MISSING_KEY_TEXT, ERROR_COLOR)
        elif not key_format_ok(text):
            self._set_status(BAD_FORMAT_TEXT, ERROR_COLOR)
        elif self._server_url:
            self._pending_key = text
            if self.task.start():
                self.render()

    def _run_test(self) -> str:
        result = self._check(self._server_url or "", self._pending_key)
        if not result.ok:
            raise SyncTestFailed(result.message)
        return result.message

    def render(self) -> None:
        """Show the test outcome once, and keep the buttons in step with the task and the server address."""
        snapshot = self.task.snapshot()
        running = snapshot.state is TaskState.RUNNING
        if snapshot is not self._shown_snapshot:
            self._shown_snapshot = snapshot
            self._show_snapshot(snapshot)
        usable = bool(self._server_url) and not running
        self.test_button.configure(state="normal" if usable else "disabled",
                                   text=TESTING_LABEL if running else TEST_LABEL)

    def _show_snapshot(self, snapshot: TaskSnapshot) -> None:
        if snapshot.state is TaskState.RUNNING:
            self._set_status(TESTING_LABEL, MUTED_COLOR)
        elif snapshot.state is TaskState.DONE:
            self._set_status(snapshot.message, SUCCESS_COLOR)
        elif snapshot.state is TaskState.FAILED:
            self._set_status(snapshot.message, ERROR_COLOR)
