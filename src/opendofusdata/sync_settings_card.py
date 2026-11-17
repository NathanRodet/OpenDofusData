"""The "Synchronisation" card of the Réglages page: the player's key and a connection test."""

import time
from collections.abc import Callable

import customtkinter

from opendofusdata.background import BackgroundTask, TaskSnapshot, TaskState
from opendofusdata.sync_address_field import AddressField
from opendofusdata.sync_counts import read_counts_text
from opendofusdata.sync_client import ConnectionResult, check_connection
from opendofusdata.sync_server_url import configured_server_url, save_server_url
from opendofusdata.sync_key import clean_key, key_format_ok, load_sync_key, save_sync_key
from opendofusdata.settings_rows import SettingRow, make_row
from opendofusdata.env_file import env_file_path
from opendofusdata.ui_theme import (
    COMPACT_BUTTON_HEIGHT, COMPACT_BUTTON_WIDTH, ERROR_COLOR, MUTED_COLOR, PADDING, ROW_WRAP, SMALL_PADDING,
    SUCCESS_COLOR, TRANSPARENT,
)
from opendofusdata.ui_widgets import make_button, make_label
from opendofusdata.window_context import WindowContext

MASK_CHARACTER = "*"
ENTRY_WIDTH = 220
TITLE = "Clé de synchronisation"
NOTE = ("Colle ici la clé de l'administrateur. Une fois enregistrée, tes prix HDV, brisages et familiers sont "
        "envoyés et ceux des autres joueurs récupérés; retire-la pour arrêter. Le test n'envoie que ta clé.")
STATUS_PREFIX = "Synchronisation: "
SHOW_LABEL = "Afficher la clé"
SAVE_LABEL = "Enregistrer"
TEST_LABEL = "Tester la connexion"
TESTING_LABEL = "Test en cours..."
SAVED_TEXT = "Clé enregistrée."
REMOVED_TEXT = "Clé retirée."
SAVE_FAILED_TEXT = "La clé n'a pas pu être enregistrée (voir le fichier de log)."
MISSING_KEY_TEXT = "Colle d'abord ta clé."
BAD_FORMAT_TEXT = "Format de clé invalide (elle ressemble à odk1.xxxxxxxxxxx.yyyy...)."
COUNTS_REFRESH_SECONDS = 5.0  # the page renders often, the counters need not follow every tick
NOT_CONFIGURED_TEXT = "Serveur de synchronisation non configuré : renseigne son adresse ci-dessus."
BAD_ADDRESS_TEXT = "Adresse invalide (https://hôte attendu, sans chemin)."
Check = Callable[[str, str], ConnectionResult]
Status = Callable[[], str]


class SyncTestFailed(Exception):
    """The connection test did not succeed; the message is what the player reads."""


class SyncSettingsCard:
    """Key field (masked), save button and connection test; nothing is sent until the test button is pressed."""

    def __init__(self, parent: customtkinter.CTkFrame, context: WindowContext, check: Check = check_connection,
                 server_url: str | None = None, status: Status = lambda: "") -> None:
        self._config_path, self._check, self._server_url = context.config_path, check, server_url
        self._worker_status, self._context = status, context
        self._counts_text, self._counts_read_at = "", float("-inf")
        self._pending_key, self._pending_url = "", ""
        self._shown_snapshot: TaskSnapshot | None = None
        self.task = BackgroundTask(self._run_test, (SyncTestFailed,))
        self._build(make_row(parent, TITLE, NOTE))
        self.render()

    def _build(self, row: SettingRow) -> None:
        self.address_field = AddressField(row.body, self._server_url)
        self.address_entry = self.address_field.entry
        line = customtkinter.CTkFrame(row.body, fg_color=TRANSPARENT, corner_radius=0)
        line.pack(fill="x")
        self.entry = customtkinter.CTkEntry(line, show=MASK_CHARACTER, width=ENTRY_WIDTH, height=COMPACT_BUTTON_HEIGHT)
        self.entry.pack(side="left")
        saved_key = load_sync_key(self._config_path)
        if saved_key:
            self.entry.insert(0, saved_key)
        self.show_box = customtkinter.CTkCheckBox(line, text=SHOW_LABEL, command=self.toggle_visibility, width=20)
        self.show_box.pack(side="left", padx=PADDING)
        self.save_button = make_button(line, SAVE_LABEL, self.save, COMPACT_BUTTON_WIDTH, COMPACT_BUTTON_HEIGHT)
        self.save_button.pack(side="left")
        self.test_button = make_button(line, TEST_LABEL, self.test, COMPACT_BUTTON_WIDTH, COMPACT_BUTTON_HEIGHT)
        self.test_button.pack(side="left", padx=SMALL_PADDING)
        self.status_label = make_label(row.body, "", color=MUTED_COLOR, anchor="w", justify="left",
                                       wraplength=ROW_WRAP)
        self.status_label.pack(fill="x", pady=(SMALL_PADDING, 0))
        self.sync_status_label = make_label(row.body, "", color=MUTED_COLOR, anchor="w", justify="left",
                                            wraplength=ROW_WRAP)
        self.sync_status_label.pack(fill="x")
        if not self._server_url:
            self._set_status(NOT_CONFIGURED_TEXT, MUTED_COLOR)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, text_color=color)

    def toggle_visibility(self) -> None:
        """Show the key in clear or mask it, following the check box."""
        self.entry.configure(show="" if self.show_box.get() else MASK_CHARACTER)

    def _save_address(self) -> bool:
        """Store the typed address when it changed; False (with a message) when it is refused or not written."""
        if not self.address_field.changed():
            return True
        text = self.address_field.text()
        if text and self.address_field.origin() is None:
            self._set_status(BAD_ADDRESS_TEXT, ERROR_COLOR)
            return False
        if not save_server_url(self._config_path, text):
            self._set_status(SAVE_FAILED_TEXT, ERROR_COLOR)
            return False
        self._server_url = configured_server_url(self._config_path, env_file_path(self._config_path))
        self.address_field.shown = text
        return True

    def save(self) -> None:
        """Save the address and the key from the fields (an empty key removes it); a malformed value is refused."""
        text = clean_key(self.entry.get())
        if not self._save_address():
            return
        if text and not key_format_ok(text):
            self._set_status(BAD_FORMAT_TEXT, ERROR_COLOR)
        elif save_sync_key(self._config_path, text or None):
            self._set_status(SAVED_TEXT if text else REMOVED_TEXT, MUTED_COLOR)
            self._render_status()
        else:
            self._set_status(SAVE_FAILED_TEXT, ERROR_COLOR)

    def test(self) -> None:
        """Test the key currently in the field (saved or not) against the server, in the background."""
        text = clean_key(self.entry.get())
        if not text:
            self._set_status(MISSING_KEY_TEXT, ERROR_COLOR)
        elif not key_format_ok(text):
            self._set_status(BAD_FORMAT_TEXT, ERROR_COLOR)
        elif self._usable_address():
            self._pending_key, self._pending_url = text, self._usable_address() or ""
            if self.task.start():
                self.render()

    def _usable_address(self) -> str | None:
        """The address to talk to: the one typed when it is valid, else the one in use."""
        return self.address_field.origin() or self._server_url

    def _run_test(self) -> str:
        result = self._check(self._pending_url, self._pending_key)
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
        self._render_status()
        usable = bool(self._usable_address()) and not running
        self.test_button.configure(state="normal" if usable else "disabled",
                                   text=TESTING_LABEL if running else TEST_LABEL)

    def _render_status(self) -> None:
        """Show the last message of the background synchronisation, if any."""
        message = self._worker_status()
        text = f"{STATUS_PREFIX}{message}" if message else ""
        counts = self._counts_line() if message else ""
        self.sync_status_label.configure(text="\n".join((text, counts)) if counts else text)

    def _counts_line(self) -> str:
        """The sent and received counters, read again at most every few seconds."""
        now = time.monotonic()
        if now - self._counts_read_at >= COUNTS_REFRESH_SECONDS:
            self._counts_read_at = now
            self._counts_text = read_counts_text(self._context.session.database_path)
        return self._counts_text

    def _show_snapshot(self, snapshot: TaskSnapshot) -> None:
        if snapshot.state is TaskState.RUNNING:
            self._set_status(TESTING_LABEL, MUTED_COLOR)
        elif snapshot.state is TaskState.DONE:
            self._set_status(snapshot.message, SUCCESS_COLOR)
        elif snapshot.state is TaskState.FAILED:
            self._set_status(snapshot.message, ERROR_COLOR)
