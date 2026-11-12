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
from opendofusdata.window_view import MENU_SIDE, MENU_TOP, PAGE_NAMES, CaptureWindow

WAIT_SECONDS = 5.0


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(WAIT_SECONDS)


def build(root, tmp_path) -> tuple[CaptureWindow, CaptureSession]:
    session = CaptureSession(str(tmp_path / "w.db"), "Brial", None, idle_capture,
                             lambda: datetime.now(timezone.utc))
    context = WindowContext(session, tmp_path / "config.json", ["Brial", "Kourial"], lambda item_id: "N/A")
    return CaptureWindow(root, context), session


def test_minimum_size_is_760_by_480(root, tmp_path) -> None:
    build(root, tmp_path)
    assert root.wm_minsize() == (MIN_WIDTH, MIN_HEIGHT) == (760, 480)


def test_menu_has_the_five_entries_in_order(root, tmp_path) -> None:
    window, _ = build(root, tmp_path)
    assert list(window.pages) == list(PAGE_NAMES) == ["HDV", "Brisage", "Familiers", "Logs", "Réglages"]
    window.show_page("Logs")
    assert window.current_page == "Logs"
    assert window.pages["Logs"].frame.winfo_manager() == "pack"
    assert window.pages["HDV"].frame.winfo_manager() == ""


def test_status_block_shows_server_counters_and_last_record(root, tmp_path) -> None:
    window, session = build(root, tmp_path)
    window.start()
    window.render()
    assert window.status_frame.status_label.cget("text") == "Capture active"
    values = {caption: label.cget("text") for caption, label in window.status_frame.values.items()}
    assert values["Serveur"] == "Brial"
    assert (values["Prix"], values["Brisages"], values["Familiers"]) == ("0", "0", "0")
    assert window.toggle_button.cget("text") == "Arrêter"
    session.stop()


def test_stop_button_then_restart(root, tmp_path) -> None:
    window, session = build(root, tmp_path)
    window.start()
    window.toggle_button.invoke()
    assert window.toggle_button.cget("text") == "Arrêt en cours..."
    assert window.toggle_button.cget("state") == "disabled"
    session.stop()
    window.render()
    assert window.toggle_button.cget("text") == "Relancer"
    session.stop()


def test_narrow_window_moves_the_menu_to_the_top(root, tmp_path) -> None:
    window, _ = build(root, tmp_path)
    assert window.menu_mode == MENU_SIDE
    window.relayout(700)
    assert window.menu_mode == MENU_TOP
    assert int(window.menu.grid_info()["columnspan"]) == 2
    window.relayout(1280)
    assert window.menu_mode == MENU_SIDE


def test_only_the_visible_page_renders(root, tmp_path) -> None:
    window, _ = build(root, tmp_path)
    calls: list[str] = []
    for name, page in window.pages.items():
        page.render = lambda snapshot, name=name: calls.append(name)
    window.show_page("Brisage")
    calls.clear()
    window.render()
    assert calls == ["Brisage"]


def test_close_stops_the_session_and_destroys_the_window(root, tmp_path) -> None:
    window, session = build(root, tmp_path)
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
    context = WindowContext(session, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")
    window = CaptureWindow(root, context)
    window.start()
    for name in PAGE_NAMES:
        window.show_page(name)
    assert session.snapshot().status is CaptureStatus.ERROR
    assert "disk full" in window.status_frame.error_label.cget("text")
