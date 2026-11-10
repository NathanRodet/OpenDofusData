"""Thin tkinter view: renders the session state and wires the buttons."""

import tkinter
from collections.abc import Callable
from tkinter import ttk

from dofus_prices.app_links import APP_NAME
from dofus_prices.capture_session import CaptureSession, CaptureStatus
from dofus_prices.window_format import (
    button_label, counts_text, last_record_text, server_text, status_text,
)

WINDOW_SIZE = "360x240"
REFRESH_MILLISECONDS = 500
PADDING = 10
LABEL_PADDING = 2
WRAP_LENGTH = 330
ONLINE_PRICES_LABEL = "Voir les prix en ligne"


class CaptureWindow:
    """Small window showing the capture state; fine to leave in the background."""

    def __init__(self, root: tkinter.Tk, session: CaptureSession, open_online: Callable[[], None]) -> None:
        self._root, self._session = root, session
        root.title(APP_NAME)
        root.geometry(WINDOW_SIZE)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._labels = {name: self._add_label() for name in ("status", "server", "counts", "last")}
        self._toggle = ttk.Button(root, command=self._toggle_capture)
        self._toggle.pack(pady=(PADDING, 0))
        ttk.Button(root, text=ONLINE_PRICES_LABEL, command=open_online).pack(pady=PADDING)

    def _add_label(self) -> ttk.Label:
        label = ttk.Label(self._root, wraplength=WRAP_LENGTH, justify="left")
        label.pack(anchor="w", padx=PADDING, pady=LABEL_PADDING)
        return label

    def start(self) -> None:
        """Start the capture and the periodic refresh."""
        self._session.start()
        self._poll()

    def _poll(self) -> None:
        self.render()
        self._root.after(REFRESH_MILLISECONDS, self._poll)

    def render(self) -> None:
        """Show the current session state."""
        snapshot = self._session.snapshot()
        self._labels["status"].configure(text=status_text(snapshot))
        self._labels["server"].configure(text=server_text(snapshot))
        self._labels["counts"].configure(text=counts_text(snapshot))
        self._labels["last"].configure(text=last_record_text(snapshot))
        self._toggle.configure(text=button_label(snapshot))

    def _toggle_capture(self) -> None:
        if self._session.snapshot().status is CaptureStatus.RUNNING:
            self._session.stop()
        else:
            self._session.start()
        self.render()

    def close(self) -> None:
        """Stop the capture cleanly, then close the window."""
        self._session.stop()
        self._root.destroy()
