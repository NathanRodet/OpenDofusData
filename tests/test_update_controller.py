"""Tests of the update controller: background check, availability and one-click install."""

from opendofusdata.app_links import RELEASES_API_URL
from opendofusdata.background import TaskState
from opendofusdata.names_fetch import NamesFetchError
from opendofusdata.update_controller import UpdateController, check_for_update
from opendofusdata.update_download import UpdateError
from opendofusdata.updates import UpdateInfo

WAIT_SECONDS = 5.0
NEW_VERSION = UpdateInfo("1.1.0", "https://github.com/NathanRodet/OpenDofusData/releases/tag/v1.1.0",
                         "https://github.com/x/OpenDofusData.exe", "https://github.com/x/OpenDofusData.exe.sha256")


def controller(check=lambda: None, install=lambda info: None, enabled=True, can_self_update=True) -> UpdateController:
    return UpdateController("1.0.0", enabled, check, install, can_self_update)


def finish_check(updates: UpdateController) -> None:
    assert updates.wait_for_check(WAIT_SECONDS)


def test_nothing_is_available_before_any_check() -> None:
    updates = controller()
    assert updates.available() is None
    assert updates.check_snapshot().state is TaskState.IDLE


def test_a_check_that_finds_a_newer_version_makes_it_available() -> None:
    updates = controller(check=lambda: NEW_VERSION)
    assert updates.start_check() is True
    finish_check(updates)
    assert updates.available() == NEW_VERSION
    assert "1.1.0" in updates.check_snapshot().message


def test_a_check_that_finds_nothing_says_the_player_is_up_to_date() -> None:
    updates = controller(check=lambda: None)
    updates.start_check()
    finish_check(updates)
    assert updates.available() is None
    assert updates.check_snapshot().state is TaskState.DONE
    assert "dernière version" in updates.check_snapshot().message


def test_a_failing_check_is_reported_and_leaves_nothing_available() -> None:
    def check() -> None:
        raise NamesFetchError("pas de réseau")

    updates = controller(check=check)
    updates.start_check()
    finish_check(updates)
    assert updates.available() is None
    assert updates.check_snapshot().state is TaskState.FAILED
    assert "pas de réseau" in updates.check_snapshot().message


def test_the_automatic_check_does_nothing_when_disabled_but_a_manual_one_runs() -> None:
    calls: list[int] = []
    updates = controller(check=lambda: calls.append(1), enabled=False)
    assert updates.start_check() is False
    assert calls == []
    assert updates.start_check(manual=True) is True
    finish_check(updates)
    assert calls == [1]


def test_an_old_result_is_cleared_by_a_new_check() -> None:
    answers = [NEW_VERSION, None]
    updates = controller(check=lambda: answers.pop(0))
    updates.start_check()
    finish_check(updates)
    updates.start_check(manual=True)
    finish_check(updates)
    assert updates.available() is None


def test_install_runs_the_installer_then_asks_for_a_restart_once() -> None:
    installed: list[UpdateInfo] = []
    updates = controller(check=lambda: NEW_VERSION, install=installed.append)
    updates.start_check()
    finish_check(updates)
    assert updates.start_install() is True
    assert updates.wait_for_install(WAIT_SECONDS)
    assert installed == [NEW_VERSION]
    assert updates.take_restart_request() is True
    assert updates.take_restart_request() is False


def test_a_failed_install_reports_the_error_and_does_not_restart() -> None:
    def install(info: UpdateInfo) -> None:
        raise UpdateError("somme de contrôle")

    updates = controller(check=lambda: NEW_VERSION, install=install)
    updates.start_check()
    finish_check(updates)
    updates.start_install()
    assert updates.wait_for_install(WAIT_SECONDS)
    assert updates.install_snapshot().state is TaskState.FAILED
    assert "somme de contrôle" in updates.install_snapshot().message
    assert updates.take_restart_request() is False


def test_install_needs_an_available_installable_update_and_a_frozen_build() -> None:
    assert controller().start_install() is False
    assert controller(check=lambda: NEW_VERSION, can_self_update=False).start_install() is False
    only_page = UpdateInfo("1.1.0", NEW_VERSION.page_url, None, None)
    updates = controller(check=lambda: only_page)
    updates.start_check()
    finish_check(updates)
    assert updates.start_install() is False


def test_check_for_update_asks_the_releases_api_once_and_reads_the_answer() -> None:
    requested: list[str] = []

    def fetch(url: str) -> object:
        requested.append(url)
        return {"tag_name": "v1.1.0", "draft": False, "prerelease": False, "html_url": NEW_VERSION.page_url,
                "assets": []}

    update = check_for_update("1.0.0", fetch)
    assert requested == [RELEASES_API_URL]
    assert update is not None
    assert update.version == "1.1.0"
    assert check_for_update("1.1.0", fetch) is None


def test_the_inert_controller_never_checks_nor_installs() -> None:
    updates = UpdateController.inert()
    assert updates.start_check() is False
    assert updates.start_install() is False
    assert updates.available() is None
