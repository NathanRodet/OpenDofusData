"""Headless-safe checks of the update UI, the names download card and the capture restart."""

import json
import threading
import time
from datetime import datetime, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.capture_session import CaptureSession, CaptureStatus
from opendofusdata.names_fetch import NamesFetchError
from opendofusdata.names_refresh import RefreshResult
from opendofusdata.page_about import AboutPage
from opendofusdata.page_settings import SettingsPage
from opendofusdata.update_controller import UpdateController
from opendofusdata.updates import UpdateInfo
from opendofusdata.window_context import WindowContext
from opendofusdata.window_view import CaptureWindow

MOMENT = datetime(2026, 11, 11, 13, 32, 5, tzinfo=timezone.utc)
WAIT_SECONDS = 5.0
PAGE_URL = "https://github.com/NathanRodet/OpenDofusData/releases/tag/v1.1.0"
INSTALLABLE = UpdateInfo("1.1.0", PAGE_URL, "https://github.com/x/O.exe", "https://github.com/x/O.exe.sha256")
PAGE_ONLY = UpdateInfo("1.1.0", PAGE_URL, None, None)


def idle_capture(pipeline, interface, stop: threading.Event) -> None:
    stop.wait(WAIT_SECONDS)


def make_context(tmp_path, updates=None) -> WindowContext:
    session = CaptureSession(str(tmp_path / "u.db"), "Brial", None, idle_capture, lambda: MOMENT)
    return WindowContext(session, lambda: None, tmp_path / "config.json", ["Brial", "Kourial"],
                         lambda item_id: "N/A", updates or UpdateController.inert(), tmp_path / "ref")


def updates_finding(info, installs=None, can_self_update=True, enabled=True) -> UpdateController:
    return UpdateController("1.0.0", enabled, lambda: info, (installs if installs is not None else []).append, can_self_update)


def checked(updates: UpdateController) -> UpdateController:
    updates.start_check()
    assert updates.wait_for_check(WAIT_SECONDS)
    return updates


def pump(root, until, seconds: float = WAIT_SECONDS) -> None:
    deadline = time.monotonic() + seconds
    while not until() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert until()


def build_about(root, context, opened=None) -> AboutPage:
    return AboutPage(root, context, (opened if opened is not None else []).append)


def test_about_offers_a_manual_check_when_nothing_is_known(root, tmp_path) -> None:
    context = make_context(tmp_path, updates_finding(INSTALLABLE))
    page = build_about(root, context)
    page.render(context.session.snapshot())
    assert page.action_button.cget("text") == "Rechercher les mises à jour"
    page.action_button.invoke()
    assert context.updates.wait_for_check(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert "1.1.0" in page.update_label.cget("text")
    assert page.action_button.cget("text") == "Mettre à jour et relancer"


def test_an_up_to_date_check_says_so(root, tmp_path) -> None:
    context = make_context(tmp_path, updates_finding(None))
    page = build_about(root, context)
    page.action_button.invoke()
    assert context.updates.wait_for_check(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert "dernière version" in page.update_label.cget("text")
    assert page.action_button.cget("text") == "Rechercher les mises à jour"


def test_an_update_that_cannot_self_install_opens_its_page(root, tmp_path) -> None:
    opened: list[str] = []
    context = make_context(tmp_path, checked(updates_finding(INSTALLABLE, can_self_update=False)))
    page = build_about(root, context, opened)
    page.render(context.session.snapshot())
    assert page.action_button.cget("text") == "Voir la version"
    page.action_button.invoke()
    assert opened == [PAGE_URL]


def test_an_update_without_files_opens_its_page(root, tmp_path) -> None:
    opened: list[str] = []
    context = make_context(tmp_path, checked(updates_finding(PAGE_ONLY)))
    page = build_about(root, context, opened)
    page.render(context.session.snapshot())
    page.action_button.invoke()
    assert opened == [PAGE_URL]


def test_one_click_installs_and_announces_the_restart(root, tmp_path) -> None:
    installs: list[UpdateInfo] = []
    context = make_context(tmp_path, checked(updates_finding(INSTALLABLE, installs)))
    page = build_about(root, context)
    page.render(context.session.snapshot())
    page.action_button.invoke()
    assert context.updates.wait_for_install(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert installs == [INSTALLABLE]
    assert "Redémarrage" in page.update_label.cget("text")


def test_a_failed_install_shows_the_error_and_allows_retrying(root, tmp_path) -> None:
    def install(info: UpdateInfo) -> None:
        raise NamesFetchError("réseau coupé")

    updates = UpdateController("1.0.0", True, lambda: INSTALLABLE, install, True)
    context = make_context(tmp_path, checked(updates))
    page = build_about(root, context)
    page.action_button.invoke()
    assert updates.wait_for_install(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert "réseau coupé" in page.update_label.cget("text")
    assert page.action_button.cget("state") == "normal"


def test_the_menu_shows_a_badge_on_a_propos_when_an_update_exists(root, tmp_path) -> None:
    context = make_context(tmp_path, checked(updates_finding(INSTALLABLE)))
    window = CaptureWindow(root, context)
    window.render()
    assert window.menu_buttons["À propos"].cget("text") == "À propos  ●"


def test_the_menu_has_no_badge_without_an_update(root, tmp_path) -> None:
    window = CaptureWindow(root, make_context(tmp_path, checked(updates_finding(None))))
    window.render()
    assert window.menu_buttons["À propos"].cget("text") == "À propos"


def test_starting_the_window_runs_the_automatic_check(root, tmp_path) -> None:
    calls: list[int] = []
    updates = UpdateController("1.0.0", True, lambda: calls.append(1), lambda info: None, True)
    context = make_context(tmp_path, updates)
    window = CaptureWindow(root, context)
    window.start()
    assert updates.wait_for_check(WAIT_SECONDS)
    assert calls == [1]
    context.session.stop()


def test_a_successful_install_closes_the_window(root, tmp_path) -> None:
    context = make_context(tmp_path, checked(updates_finding(INSTALLABLE)))
    window = CaptureWindow(root, context)
    window.start()
    context.updates.start_install()
    assert context.updates.wait_for_install(WAIT_SECONDS)
    window.render()
    pump(root, lambda: not root.winfo_exists())
    assert context.session.snapshot().status is CaptureStatus.STOPPED


def test_restart_capture_applies_the_pending_server(root, tmp_path) -> None:
    context = make_context(tmp_path)
    window = CaptureWindow(root, context)
    window.start()
    context.session.apply_settings(context.session.database_path, "Kourial")
    window.restart_capture()
    pump(root, lambda: context.session.snapshot().status is CaptureStatus.RUNNING
         and context.session.snapshot().server == "Kourial")
    context.session.stop()


def settings(root, context, refresh=None) -> SettingsPage:
    return SettingsPage(root, context, lambda current: None, refresh or (lambda path, directory: RefreshResult(3, 1)))


def test_names_card_reports_that_no_names_are_loaded(root, tmp_path) -> None:
    page = settings(root, make_context(tmp_path))
    assert "Aucun nom chargé" in page.names_card.status_label.cget("text")


def test_names_download_loads_names_and_swaps_the_lookup(root, tmp_path) -> None:
    context = make_context(tmp_path)
    before = context.name_of
    page = settings(root, context)
    page.names_card.button.invoke()
    assert page.names_card.task.wait(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert "3 objets" in page.names_card.status_label.cget("text")
    assert context.name_of is not before
    assert page.names_card.button.cget("state") == "normal"


def test_names_download_failure_is_shown_and_keeps_the_lookup(root, tmp_path) -> None:
    def refresh(path, directory):
        raise NamesFetchError("API indisponible")

    context = make_context(tmp_path)
    before = context.name_of
    page = settings(root, context, refresh)
    page.names_card.button.invoke()
    assert page.names_card.task.wait(WAIT_SECONDS)
    page.render(context.session.snapshot())
    assert "API indisponible" in page.names_card.status_label.cget("text")
    assert context.name_of is before


def test_the_update_check_switch_is_saved_and_applied(root, tmp_path) -> None:
    updates = updates_finding(None)
    context = make_context(tmp_path, updates)
    page = settings(root, context)
    assert page.update_switch.get() == 1
    page.update_switch.toggle()
    assert updates.enabled is False
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["check_updates"] is False


def test_changing_the_server_while_running_restarts_the_capture(root, tmp_path) -> None:
    restarts: list[int] = []
    context = make_context(tmp_path)
    context.restart_capture = lambda: restarts.append(1)
    page = settings(root, context)
    context.session.start()
    page.choose_server("Kourial")
    assert restarts == [1]
    assert "redémarre" in page.message_label.cget("text")
    context.session.stop()


def test_changing_the_server_while_stopped_does_not_restart_anything(root, tmp_path) -> None:
    restarts: list[int] = []
    context = make_context(tmp_path)
    context.restart_capture = lambda: restarts.append(1)
    settings(root, context).choose_server("Kourial")
    assert restarts == []
