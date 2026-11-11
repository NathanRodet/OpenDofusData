"""The Accueil page: capture state, server, counters and the link to the online prices."""

from collections.abc import Callable

import customtkinter

from opendofusdata.capture_session import CaptureStatus, SessionSnapshot
from opendofusdata.ui_theme import (
    DOT_SIZE, ERROR_COLOR, HEADLINE_SIZE, MUTED_COLOR, OFF_COLOR, PADDING, SUCCESS_COLOR, TINY_PADDING, WRAP_LENGTH,
)
from opendofusdata.ui_widgets import make_button, make_card, make_label, make_page
from opendofusdata.window_format import (
    counts_text, error_detail_text, headline_text, last_record_text, server_text,
)

DOT = "●"
ONLINE_PRICES_LABEL = "Voir les prix en ligne"
STATUS_COLORS = {
    CaptureStatus.RUNNING: SUCCESS_COLOR,
    CaptureStatus.STOPPING: OFF_COLOR,
    CaptureStatus.STOPPED: OFF_COLOR,
    CaptureStatus.ERROR: ERROR_COLOR,
}


class HomePage:
    """Shows the capture state at a glance."""

    def __init__(self, parent: customtkinter.CTkBaseClass, open_online: Callable[[], None]) -> None:
        self.frame, body = make_page(parent)
        self.dot_label = make_label(body, DOT, DOT_SIZE)
        self.dot_label.pack(pady=(PADDING, 0))
        self.status_label = make_label(body, "", HEADLINE_SIZE, bold=True)
        self.status_label.pack()
        self.server_label = make_label(body, "", color=MUTED_COLOR)
        self.server_label.pack(pady=(TINY_PADDING, PADDING))
        self.error_label = make_label(body, "", color=ERROR_COLOR, wraplength=WRAP_LENGTH, justify="left")
        self.error_label.pack(pady=(0, PADDING))
        card = make_card(body)
        self.counts_label = make_label(card, "", anchor="w", justify="left")
        self.counts_label.pack(fill="x", padx=PADDING, pady=(PADDING, TINY_PADDING))
        self.last_label = make_label(card, "", anchor="w")
        self.last_label.pack(fill="x", padx=PADDING, pady=(0, PADDING))
        self.online_button = make_button(body, ONLINE_PRICES_LABEL, open_online)
        self.online_button.pack(pady=PADDING)

    def render(self, snapshot: SessionSnapshot) -> None:
        """Show the current session state."""
        self.dot_label.configure(text_color=STATUS_COLORS[snapshot.status])
        self.status_label.configure(text=headline_text(snapshot))
        self.server_label.configure(text=server_text(snapshot))
        self.error_label.configure(text=error_detail_text(snapshot))
        self.counts_label.configure(text=counts_text(snapshot))
        self.last_label.configure(text=last_record_text(snapshot))
