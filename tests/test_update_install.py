"""Tests of the update install step (fake download and launch)."""

from pathlib import Path

import pytest

from opendofusdata.update_download import UpdateError
from opendofusdata.update_install import install_update
from opendofusdata.updates import UpdateInfo

INFO = UpdateInfo("1.1.0", "https://github.com/x/r", "https://github.com/x/O.exe", "https://github.com/x/O.sha256")


def test_the_download_goes_next_to_the_given_folder_then_the_swap_is_launched(tmp_path) -> None:
    seen: list[object] = []
    downloaded = tmp_path / "O.exe.new"
    install_update(INFO, tmp_path, lambda info, folder: seen.append((info, folder)) or downloaded, seen.append)
    assert seen == [(INFO, tmp_path), downloaded]


def test_a_failed_verification_does_not_launch_anything(tmp_path) -> None:
    launched: list[Path] = []

    def download(info: UpdateInfo, folder: Path) -> Path:
        raise UpdateError("somme de contrôle")

    with pytest.raises(UpdateError, match="somme de contrôle"):
        install_update(INFO, tmp_path, download, launched.append)
    assert launched == []


def test_an_unwritable_folder_becomes_a_french_error_and_launches_nothing(tmp_path) -> None:
    launched: list[Path] = []

    def download(info: UpdateInfo, folder: Path) -> Path:
        raise PermissionError("accès refusé")

    with pytest.raises(UpdateError, match="Impossible d'écrire"):
        install_update(INFO, tmp_path, download, launched.append)
    assert launched == []
