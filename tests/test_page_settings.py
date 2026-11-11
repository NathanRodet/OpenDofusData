"""Headless-safe checks of the Réglages and À propos pages (skipped when no display is available)."""

import json
import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata import __version__
from opendofusdata.capture_session import CaptureSession
from opendofusdata.page_about import AboutPage
from opendofusdata.page_settings import SettingsPage
from opendofusdata.window_context import WindowContext

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(2.0)


def make_context(tmp_path, config_path=None) -> WindowContext:
    session = CaptureSession(str(tmp_path / "old.db"), "Brial", None, idle_capture, lambda: MOMENT)
    return WindowContext(session, lambda: None, config_path or tmp_path / "config.json",
                         ["Brial", "Kourial"], lambda item_id: "N/A")


def saved_config(tmp_path) -> dict[str, object]:
    return json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))


def test_server_choice_is_saved_and_applied(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = SettingsPage(root, context, lambda current: None)
    page.choose_server("Kourial")
    assert saved_config(tmp_path)["server"] == "Kourial"
    context.session.start()
    assert context.session.snapshot().server == "Kourial"
    context.session.stop()


def test_database_choice_is_saved_and_applied(root, tmp_path) -> None:
    new_path = str(tmp_path / "chosen.db")
    context = make_context(tmp_path)
    page = SettingsPage(root, context, lambda current: new_path)
    page.change_database()
    assert saved_config(tmp_path)["database_path"] == new_path
    assert context.session.database_path == new_path
    assert page.database_label.cget("text") == new_path


def test_cancelled_file_dialog_changes_nothing(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = SettingsPage(root, context, lambda current: None)
    page.change_database()
    assert not (tmp_path / "config.json").exists()
    assert context.session.database_path == str(tmp_path / "old.db")


def test_message_asks_restart_while_running_and_not_when_stopped(root, tmp_path) -> None:
    context = make_context(tmp_path)
    page = SettingsPage(root, context, lambda current: None)
    page.choose_server("Kourial")
    assert page.message_label.cget("text") == "Enregistré."
    context.session.start()
    page.choose_server("Brial")
    assert "redémarre" in page.message_label.cget("text")
    context.session.stop()


def test_unwritable_config_reports_an_error_and_keeps_the_state(root, tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder", encoding="utf-8")
    context = make_context(tmp_path, blocker / "config.json")
    page = SettingsPage(root, context, lambda current: None)
    page.choose_server("Kourial")
    assert "pas pu être enregistré" in page.message_label.cget("text")
    assert context.session.snapshot().server == "Brial"


def test_current_server_missing_from_the_list_is_still_shown(root, tmp_path) -> None:
    session = CaptureSession(str(tmp_path / "x.db"), "Inconnu", None, idle_capture, lambda: MOMENT)
    context = WindowContext(session, lambda: None, tmp_path / "config.json", ["Brial"], lambda item_id: "N/A")
    assert SettingsPage(root, context, lambda current: None).server_menu.get() == "Inconnu"


def test_about_page_names_the_app_and_says_nothing_is_sent(root, tmp_path) -> None:
    page = AboutPage(root, make_context(tmp_path), lambda url: None)
    assert "Rien n'est envoyé" in page.summary_label.cget("text")
    assert page.version_label.cget("text") == f"Version {__version__}"


def test_changing_the_database_keeps_the_server_chosen_before(root, tmp_path) -> None:
    new_path = str(tmp_path / "chosen.db")
    context = make_context(tmp_path)
    page = SettingsPage(root, context, lambda current: new_path)
    page.choose_server("Kourial")
    page.change_database()
    context.session.start()
    assert context.session.snapshot().server == "Kourial"
    assert context.session.database_path == new_path
    context.session.stop()


def test_changing_the_database_replaces_the_name_lookup(root, tmp_path) -> None:
    context = make_context(tmp_path)
    before = context.name_of
    SettingsPage(root, context, lambda current: str(tmp_path / "chosen.db")).change_database()
    assert context.name_of is not before
