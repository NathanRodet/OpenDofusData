"""The list of generated keys in the Administration tab: one row per key, with its two actions."""

from collections.abc import Callable

import customtkinter

from opendofusdata.admin_registry import KeyEntry
from opendofusdata.ui_theme import (
    ACCENT_COLOR, ACCENT_HOVER_COLOR, BUTTON_HEIGHT, CORNER_RADIUS, ERROR_COLOR, MUTED_COLOR, PADDING, SUCCESS_COLOR,
    TINY_PADDING, TRANSPARENT,
)
from opendofusdata.ui_widgets import make_label

COPY_LABEL = "Copier la clé"
REVOKE_LABEL = "Révoquer"
REVOKE_PURGE_LABEL = "Révoquer et supprimer ses relevés"
ACTIVE_TEXT = "Active"
REVOKED_TEXT = "Révoquée le {date}"
DATE_LENGTH = 10  # YYYY-MM-DD out of the ISO timestamp
ROW_BUTTON_WIDTH = 110
WIDE_BUTTON_WIDTH = 230
KeyAction = Callable[[str], None]


def status_text(entry: KeyEntry) -> str:
    """"Active", or the day the key was revoked."""
    if entry.revoked_at is None:
        return ACTIVE_TEXT
    return REVOKED_TEXT.format(date=entry.revoked_at[:DATE_LENGTH])


class AdminRows(customtkinter.CTkFrame):
    """Rebuilt only when the entries change; each row copies or revokes the key it shows."""

    def __init__(self, parent: customtkinter.CTkBaseClass, on_copy: KeyAction, on_revoke: KeyAction,
                 on_revoke_purge: KeyAction) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._on_copy, self._on_revoke, self._on_revoke_purge = on_copy, on_revoke, on_revoke_purge
        self.entries: list[KeyEntry] = []
        self._status_labels: dict[str, customtkinter.CTkLabel] = {}

    def set_entries(self, entries: list[KeyEntry]) -> None:
        """Show these entries (nothing is redrawn when they are the ones already shown)."""
        if entries == self.entries:
            return
        self.entries = list(entries)
        self._status_labels = {}
        for child in self.winfo_children():
            child.destroy()
        for row, entry in enumerate(self.entries):
            self._add_row(row, entry)

    def status_of(self, key_id: str) -> str:
        """The status text shown for this key."""
        return str(self._status_labels[key_id].cget("text"))

    def _add_row(self, row: int, entry: KeyEntry) -> None:
        revoked = entry.revoked_at is not None
        padding = {"padx": PADDING, "pady": TINY_PADDING}
        make_label(self, entry.label, anchor="w").grid(row=row, column=0, sticky="w", **padding)
        make_label(self, entry.created_at[:DATE_LENGTH], color=MUTED_COLOR).grid(row=row, column=1, **padding)
        status = make_label(self, status_text(entry), color=ERROR_COLOR if revoked else SUCCESS_COLOR)
        status.grid(row=row, column=2, **padding)
        self._status_labels[entry.key_id] = status
        self._button(COPY_LABEL, self._on_copy, entry.key_id, not revoked).grid(row=row, column=3, **padding)
        self._button(REVOKE_LABEL, self._on_revoke, entry.key_id, not revoked).grid(row=row, column=4, **padding)
        self._button(REVOKE_PURGE_LABEL, self._on_revoke_purge, entry.key_id, not revoked,
                     WIDE_BUTTON_WIDTH).grid(row=row, column=5, **padding)

    def _button(self, text: str, action: KeyAction, key_id: str, enabled: bool,
                width: int = ROW_BUTTON_WIDTH) -> customtkinter.CTkButton:
        return customtkinter.CTkButton(
            self, text=text, width=width, height=BUTTON_HEIGHT, corner_radius=CORNER_RADIUS,
            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER_COLOR, state="normal" if enabled else "disabled",
            command=lambda: action(key_id))
