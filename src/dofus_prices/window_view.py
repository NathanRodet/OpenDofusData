"""Thin tkinter view: renders the session state and wires the buttons."""

import logging
import tkinter
from collections.abc import Callable
from tkinter import ttk

from dofus_prices.app_links import APP_NAME
from dofus_prices.capture_session import CaptureSession, CaptureStatus
from dofus_prices.window_format import (
    button_enabled, button_label, counts_text, last_record_text, server_text, status_text,
)

logger = logging.getLogger(__name__)

WINDOW_SIZE = "360x240"
REFRESH_MILLISECONDS = 500
CLOSE_POLL_MILLISECONDS = 100
PADDING = 10
LABEL_PADDING = 2
WRAP_LENGTH = 330
ONLINE_PRICES_LABEL = "Voir les prix en ligne"
LABEL_NAMES = ("status", "server", "counts", "last")


class CaptureWindow:
    """Small window showing the capture state; fine to leave in the background."""

    def __init__(self, root: tkinter.Tk, session: CaptureSession, open_online: Callable[[], None]) -> None:
        self._root, self._session = root, session
        root.title(APP_NAME)
        root.geometry(WINDOW_SIZE)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.labels = {name: self._add_label() for name in LABEL_NAMES}
        self.toggle_button = ttk.Button(root, command=self._toggle_capture)
        self.toggle_button.pack(pady=(PADDING, 0))
        self.online_button = ttk.Button(root, text=ONLINE_PRICES_LABEL, command=open_online)
        self.online_button.pack(pady=PADDING)

    def _add_label(self) -> ttk.Label:
        label = ttk.Label(self._root, wraplength=WRAP_LENGTH, justify="left")
        label.pack(anchor="w", padx=PADDING, pady=LABEL_PADDING)
        return label

    def start(self) -> None:
        """Start the capture and the periodic refresh."""
        self._session.start()
        self._poll()

    def _poll(self) -> None:
        try:
            self.render()
        except Exception:  # keep refreshing whatever happens to one render
            logger.exception("window refresh failed")
        finally:
            self._root.after(REFRESH_MILLISECONDS, self._poll)

    def render(self) -> None:
        """Show the current session state."""
        snapshot = self._session.snapshot()
        texts = (status_text, server_text, counts_text, last_record_text)
        for name, text_of in zip(LABEL_NAMES, texts):
            self.labels[name].configure(text=text_of(snapshot))
        self.toggle_button.configure(text=button_label(snapshot))
        self.toggle_button.state(["!disabled"] if button_enabled(snapshot) else ["disabled"])

    def _toggle_capture(self) -> None:
        if self._session.snapshot().status is CaptureStatus.RUNNING:
            self._session.request_stop()
        else:
            self._session.start()
        self.render()

    def close(self) -> None:
        """Ask the capture to stop, wait for it without freezing the window, then close."""
        self._session.request_stop()
        self._close_when_stopped()

    def _close_when_stopped(self) -> None:
        if self._session.snapshot().status is CaptureStatus.STOPPING:
            self._root.after(CLOSE_POLL_MILLISECONDS, self._close_when_stopped)
        else:
            self._root.destroy()
