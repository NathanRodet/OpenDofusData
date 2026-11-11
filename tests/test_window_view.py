"""Headless-safe checks of the CustomTkinter window (skipped when no display is available)."""

import threading
import time
from datetime import datetime, timezone

import pytest

tkinter = pytest.importorskip("tkinter")
customtkinter = pytest.importorskip("customtkinter")

from opendofusdata.capture_session import CaptureSession, CaptureStatus
from opendofusdata.ui_theme import MIN_HEIGHT, MIN_WIDTH
from opendofusdata.window_context import WindowContext
from opendofusdata.window_view import PAGE_NAMES, CaptureWindow

WAIT_SECONDS = 5.0


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(WAIT_SECONDS)


def build(root, tmp_path, opened: list[int]) -> tuple[CaptureWindow, CaptureSession]:
    session = CaptureSession(str(tmp_path / "w.db"), "Brial", None, idle_capture,
                             lambda: datetime.now(timezone.utc))
    context = WindowContext(session, lambda: opened.append(1), tmp_path / "config.json",
                            ["Brial", "Kourial"], lambda item_id: "N/A")
    return CaptureWindow(root, context), session


def test_minimum_size_is_at_least_640_by_400(root, tmp_path) -> None:
    build(root, tmp_path, [])
    width, height = root.wm_minsize()
    assert width >= MIN_WIDTH
    assert height >= MIN_HEIGHT


def test_menu_has_the_five_pages_and_switches(root, tmp_path) -> None:
    window, _ = build(root, tmp_path, [])
    assert list(window.pages) == list(PAGE_NAMES) == ["Accueil", "Données", "Logs", "Réglages", "À propos"]
    window.show_page("Logs")
    assert window.current_page == "Logs"
    assert window.pages["Logs"].frame.winfo_manager() == "pack"
    assert window.pages["Accueil"].frame.winfo_manager() == ""


def test_home_shows_status_and_counts(root, tmp_path) -> None:
    window, session = build(root, tmp_path, [])
    window.start()
    window.render()
    home = window.pages["Accueil"]
    assert home.status_label.cget("text") == "Capture active"
    assert home.server_label.cget("text") == "Serveur : Brial"
    assert "Prix enregistrés : 0" in home.counts_label.cget("text")
    assert window.toggle_button.cget("text") == "Arrêter"
    session.stop()


def test_stop_button_then_restart(root, tmp_path) -> None:
    window, session = build(root, tmp_path, [])
    window.start()
    window.toggle_button.invoke()
    assert window.toggle_button.cget("text") == "Arrêt en cours..."
    assert window.toggle_button.cget("state") == "disabled"
    session.stop()
    window.render()
    assert window.toggle_button.cget("text") == "Relancer"
    session.stop()


def test_online_button_calls_the_opener(root, tmp_path) -> None:
    opened: list[int] = []
    window, _ = build(root, tmp_path, opened)
    window.pages["Accueil"].online_button.invoke()
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
    assert session.snapshot().status is CaptureStatus.STOPPED


def failing_writer(path: str):
    raise OSError("disk full")


def test_every_page_renders_while_the_session_is_in_error(root, tmp_path) -> None:
    session = CaptureSession(str(tmp_path / "e.db"), "Brial", None, idle_capture,
                             lambda: datetime.now(timezone.utc), writer_factory=failing_writer)
    context = WindowContext(session, lambda: None, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")
    window = CaptureWindow(root, context)
    window.start()
    for name in PAGE_NAMES:
        window.show_page(name)
    window.show_page("Accueil")
    assert session.snapshot().status is CaptureStatus.ERROR
    assert "disk full" in window.pages["Accueil"].error_label.cget("text")
