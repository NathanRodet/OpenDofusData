"""The list of generated keys in the Administration tab: one row per key (name, date, status, actions)."""

from collections.abc import Callable

import customtkinter

from opendofusdata.admin_registry import KeyEntry
from opendofusdata.ui_theme import (
    COMPACT_BUTTON_HEIGHT, CORNER_RADIUS, DIVIDER_COLOR, ERROR_COLOR, MUTED_COLOR, PADDING, SMALL_PADDING,
    SUCCESS_COLOR, TRANSPARENT,
)
from opendofusdata.ui_widgets import make_button, make_label

COPY_LABEL = "Copier"
REVOKE_LABEL = "Révoquer"
REVOKE_PURGE_LABEL = "Révoquer et purger"
EMPTY_TEXT = "Aucune clé pour l'instant. Saisis un pseudo plus haut pour en créer une."
ACTIVE_TEXT = "Active"
REVOKED_TEXT = "Révoquée le {date}"
CREATED_TEXT = "Créée le {date}"
DATE_LENGTH = 10  # YYYY-MM-DD out of the ISO timestamp
COPY_WIDTH = 80
REVOKE_WIDTH = 90
PURGE_WIDTH = 140
DANGER_HOVER_COLOR = "#4a2b2b"
KeyAction = Callable[[str], None]


def status_text(entry: KeyEntry) -> str:
    """"Active", or the day the key was revoked."""
    if entry.revoked_at is None:
        return ACTIVE_TEXT
    return REVOKED_TEXT.format(date=entry.revoked_at[:DATE_LENGTH])


def make_danger_button(parent: customtkinter.CTkBaseClass, text: str, command: Callable[[], None],
                       width: int) -> customtkinter.CTkButton:
    """An outlined red button: an action that cannot be undone."""
    return customtkinter.CTkButton(
        parent, text=text, command=command, width=width, height=COMPACT_BUTTON_HEIGHT, corner_radius=CORNER_RADIUS,
        fg_color=TRANSPARENT, border_width=1, border_color=ERROR_COLOR, text_color=ERROR_COLOR,
        hover_color=DANGER_HOVER_COLOR)


class AdminRows(customtkinter.CTkFrame):
    """Rebuilt only when the entries change; each row copies or revokes the key it shows."""

    def __init__(self, parent: customtkinter.CTkBaseClass, on_copy: KeyAction, on_revoke: KeyAction,
                 on_revoke_purge: KeyAction) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._on_copy, self._on_revoke, self._on_revoke_purge = on_copy, on_revoke, on_revoke_purge
        self.entries: list[KeyEntry] = []
        self._status_labels: dict[str, customtkinter.CTkLabel] = {}
        self._show_empty_text()

    def set_entries(self, entries: list[KeyEntry]) -> None:
        """Show these entries (nothing is redrawn when they are the ones already shown)."""
        if entries == self.entries:
            return
        self.entries = list(entries)
        self._status_labels = {}
        for child in self.winfo_children():
            child.destroy()
        for position, entry in enumerate(self.entries):
            self._add_row(entry, divider=position > 0)
        if not self.entries:
            self._show_empty_text()

    def status_of(self, key_id: str) -> str:
        """The status text shown for this key."""
        return str(self._status_labels[key_id].cget("text"))

    def _show_empty_text(self) -> None:
        make_label(self, EMPTY_TEXT, color=MUTED_COLOR, anchor="w", justify="left").pack(
            fill="x", padx=PADDING, pady=PADDING)

    def _add_row(self, entry: KeyEntry, divider: bool) -> None:
        if divider:
            customtkinter.CTkFrame(self, width=1, height=1, fg_color=DIVIDER_COLOR, corner_radius=0).pack(
                fill="x", padx=PADDING)
        row = customtkinter.CTkFrame(self, fg_color=TRANSPARENT, corner_radius=0)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1)
        self._add_texts(row, entry)
        if entry.revoked_at is None:
            self._add_actions(row, entry.key_id)

    def _add_texts(self, row: customtkinter.CTkFrame, entry: KeyEntry) -> None:
        make_label(row, entry.label, bold=True, anchor="w").grid(
            row=0, column=0, sticky="w", padx=PADDING, pady=(SMALL_PADDING, 0))
        revoked = entry.revoked_at is not None
        status = make_label(row, status_text(entry), color=ERROR_COLOR if revoked else SUCCESS_COLOR, anchor="w")
        status.grid(row=0, column=1, sticky="w", padx=SMALL_PADDING, pady=(SMALL_PADDING, 0))
        self._status_labels[entry.key_id] = status
        make_label(row, CREATED_TEXT.format(date=entry.created_at[:DATE_LENGTH]), 12, color=MUTED_COLOR,
                   anchor="w").grid(row=1, column=0, sticky="w", padx=PADDING, pady=(0, SMALL_PADDING))

    def _add_actions(self, row: customtkinter.CTkFrame, key_id: str) -> None:
        actions = customtkinter.CTkFrame(row, fg_color=TRANSPARENT, corner_radius=0, width=1, height=1)
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=PADDING)
        make_button(actions, COPY_LABEL, lambda: self._on_copy(key_id), COPY_WIDTH, COMPACT_BUTTON_HEIGHT).pack(
            side="left", padx=(0, SMALL_PADDING))
        make_danger_button(actions, REVOKE_LABEL, lambda: self._on_revoke(key_id), REVOKE_WIDTH).pack(
            side="left", padx=(0, SMALL_PADDING))
        make_danger_button(actions, REVOKE_PURGE_LABEL, lambda: self._on_revoke_purge(key_id), PURGE_WIDTH).pack(
            side="left")
