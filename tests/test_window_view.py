"""Headless-safe checks of the tkinter view (skipped when no display is available)."""

import threading
from datetime import datetime, timezone

import pytest

tkinter = pytest.importorskip("tkinter")

from dofus_prices.capture_session import CaptureSession
from dofus_prices.window_view import CaptureWindow


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(5.0)


def test_window_builds_renders_and_closes(tmp_path) -> None:
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        pytest.skip(f"no display available: {error}")
    opened: list[int] = []
    session = CaptureSession(str(tmp_path / "w.db"), "Brial", None, idle_capture,
                             lambda: datetime.now(timezone.utc))
    window = CaptureWindow(root, session, lambda: opened.append(1))
    window.start()
    window.render()
    window.close()
    assert session.snapshot().status.value == "stopped"
