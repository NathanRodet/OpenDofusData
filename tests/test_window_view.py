"""Headless-safe checks of the tkinter view (skipped when no display is available)."""

import threading
import time
from datetime import datetime, timezone

import pytest

tkinter = pytest.importorskip("tkinter")

from dofus_prices.capture_session import CaptureSession
from dofus_prices.window_view import CaptureWindow

WAIT_SECONDS = 5.0


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(WAIT_SECONDS)


@pytest.fixture(scope="module")
def tk_root():
    """One Tk interpreter for the module (a second one fails to init on some Windows setups)."""
    try:
        interpreter = tkinter.Tk()
    except tkinter.TclError as error:
        pytest.skip(f"no display available: {error}")
    interpreter.withdraw()
    yield interpreter
    interpreter.destroy()


@pytest.fixture
def root(tk_root):
    window_root = tkinter.Toplevel(tk_root)
    yield window_root
    if window_root.winfo_exists():
        window_root.destroy()


def build(root, tmp_path, opened: list[int]) -> tuple[CaptureWindow, CaptureSession]:
    session = CaptureSession(str(tmp_path / "w.db"), "Brial", None, idle_capture,
                             lambda: datetime.now(timezone.utc))
    return CaptureWindow(root, session, lambda: opened.append(1)), session


def test_renders_state_texts_and_button_label(root, tmp_path) -> None:
    window, session = build(root, tmp_path, [])
    window.start()
    window.render()
    assert window.labels["status"].cget("text") == "Capture active"
    assert window.labels["server"].cget("text") == "Serveur : Brial"
    assert "Prix enregistrés : 0" in window.labels["counts"].cget("text")
    assert window.toggle_button.cget("text") == "Arrêter"
    session.stop()


def test_stop_button_then_restart(root, tmp_path) -> None:
    window, session = build(root, tmp_path, [])
    window.start()
    window.toggle_button.invoke()
    assert window.toggle_button.cget("text") == "Arrêt en cours..."
    assert window.toggle_button.instate(["disabled"])
    session.stop()
    window.render()
    assert window.toggle_button.cget("text") == "Relancer"
    session.stop()


def test_online_button_calls_the_opener(root, tmp_path) -> None:
    opened: list[int] = []
    window, session = build(root, tmp_path, opened)
    window.online_button.invoke()
    assert opened == [1]


def test_close_stops_the_session_and_destroys_the_window(root, tmp_path) -> None:
    window, session = build(root, tmp_path, [])
    window.start()
    window.close()
    deadline = time.monotonic() + WAIT_SECONDS
    while root.winfo_exists() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert not root.winfo_exists()
    assert session.snapshot().status.value == "stopped"
