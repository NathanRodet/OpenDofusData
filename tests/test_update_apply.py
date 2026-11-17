"""Tests of the restart-with-the-new-exe helper (one test runs the real PowerShell helper)."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from opendofusdata.update_apply import can_self_update, launch_replacement, replacement_script


def test_the_script_waits_for_the_process_then_moves_then_restarts() -> None:
    script = replacement_script(Path("C:/Apps/O.exe.new"), Path("C:/Apps/O.exe"), 4242)
    assert script.index("4242") < script.index("Move-Item") < script.index("Start-Process")
    assert f"'{Path('C:/Apps/O.exe.new')}'" in script
    assert f"'{Path('C:/Apps/O.exe')}'" in script


def test_single_quotes_in_paths_are_escaped() -> None:
    script = replacement_script(Path("C:/Mes apps/l'outil.new"), Path("C:/Mes apps/l'outil.exe"), 1)
    assert "l''outil.new" in script
    assert "l''outil.exe" in script


def test_launch_runs_a_detached_hidden_powershell_with_a_reset_environment() -> None:
    seen: dict[str, object] = {}

    def spawn(arguments, **options):
        seen["arguments"] = arguments
        seen.update(options)

    launch_replacement(Path("a.new"), Path("a.exe"), 7, spawn=spawn, environ={"PATH": "x"})
    arguments = seen["arguments"]
    assert arguments[0].lower().startswith("powershell")
    assert "-NoProfile" in arguments
    assert seen["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert seen["env"]["PATH"] == "x"
    assert seen["creationflags"] != 0
    assert seen["close_fds"] is True


def test_self_update_is_only_possible_from_a_frozen_windows_build(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert can_self_update() is False
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert can_self_update() is True
    monkeypatch.setattr(sys, "platform", "linux")
    assert can_self_update() is False


@pytest.mark.skipif(sys.platform != "win32", reason="the replacement helper is PowerShell on Windows")
def test_the_real_helper_replaces_the_old_file(tmp_path) -> None:
    """Regression: with DETACHED_PROCESS PowerShell exited without running anything."""
    finished = subprocess.Popen([sys.executable, "-c", "pass"])
    finished.wait()
    target, new = tmp_path / "OpenDofusData.exe", tmp_path / "OpenDofusData-9.exe.new"
    target.write_text("old")
    new.write_text("new")
    launch_replacement(new, target, finished.pid)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and target.read_text() != "new":
        time.sleep(0.2)
    assert target.read_text() == "new" and not new.exists()
