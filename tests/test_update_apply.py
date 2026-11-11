"""Tests of the restart-with-the-new-exe helper (no process is really started)."""

import sys
from pathlib import Path

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
