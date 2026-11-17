"""The capture status block at the bottom of the window menu."""

from datetime import datetime

import customtkinter

from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.ui_theme import (
    DOT_SIZE, ERROR_COLOR, MUTED_COLOR, OFF_COLOR, SIDEBAR_WIDTH, SMALL_PADDING, SUCCESS_COLOR, PADDING, TINY_PADDING,
    TRANSPARENT,
)
from opendofusdata.ui_widgets import make_label
from opendofusdata.window_format import error_detail_text, headline_text, status_rows

DOT = "●"
CAPTIONS = ("Serveur", "Prix", "Brisages", "Familiers", "Dernier relevé", "Références", "Synchro")
STATUS_COLORS = {
    CaptureStatus.RUNNING: SUCCESS_COLOR,
    CaptureStatus.STOPPING: OFF_COLOR,
    CaptureStatus.STOPPED: OFF_COLOR,
    CaptureStatus.ERROR: ERROR_COLOR,
}


class StatusBlock(customtkinter.CTkFrame):
    """A coloured dot with the capture state, then the server, the counters and the last record."""

    def __init__(self, parent: customtkinter.CTkBaseClass) -> None:
        super().__init__(parent, fg_color=TRANSPARENT)
        head = customtkinter.CTkFrame(self, fg_color=TRANSPARENT)
        head.pack(fill="x")
        self.dot_label = make_label(head, DOT, DOT_SIZE // 2)
        self.dot_label.pack(side="left")
        self.status_label = make_label(head, "", bold=True)
        self.status_label.pack(side="left", padx=SMALL_PADDING)
        self.error_label = make_label(self, "", color=ERROR_COLOR, anchor="w", justify="left",
                                      wraplength=SIDEBAR_WIDTH - 2 * PADDING)
        self.error_label.pack(fill="x")
        self.values = {caption: self._add_row(caption) for caption in CAPTIONS}

    def _add_row(self, caption: str) -> customtkinter.CTkLabel:
        row = customtkinter.CTkFrame(self, fg_color=TRANSPARENT)
        row.pack(fill="x", pady=TINY_PADDING)
        make_label(row, caption, color=MUTED_COLOR).pack(side="left")
        value = make_label(row, "")
        value.pack(side="right")
        return value

    def render(self, snapshot: SessionSnapshot, now: datetime, extra: dict[str, str] | None = None) -> None:
        """Show the session state, then the extra lines (reference data, synchronisation) the window computed."""
        self.dot_label.configure(text_color=STATUS_COLORS[snapshot.status])
        self.status_label.configure(text=headline_text(snapshot))
        self.error_label.configure(text=error_detail_text(snapshot))
        for caption, value in status_rows(snapshot, now):
            self.values[caption].configure(text=value)
        for caption, value in (extra or {}).items():
            self.values[caption].configure(text=value)
