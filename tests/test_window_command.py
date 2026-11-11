"""Tests for the window command wiring (no real display needed)."""

import argparse
import subprocess
import sys
import tkinter
from pathlib import Path

from opendofusdata import window_command as module
from opendofusdata.capture_errors import EXIT_FAILED, EXIT_OK

SOURCE_DIRECTORY = Path(__file__).resolve().parent.parent / "src"
LAZY_TKINTER_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); sys.modules['tkinter'] = None; "
    "import opendofusdata.cli as cli; "
    "sys.exit(cli.run(['prices', '--help'], lambda pipeline, interface: None))"
)


class FakeSession:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


def test_no_display_gives_a_clear_failure(monkeypatch, capsys) -> None:
    def no_display() -> None:
        raise tkinter.TclError("no display name")

    monkeypatch.setattr(tkinter, "Tk", no_display)
    assert module.show_window(FakeSession(), lambda: None) == EXIT_FAILED
    assert "no display name" in capsys.readouterr().err


def test_session_is_stopped_after_the_main_loop(monkeypatch) -> None:
    events: list[str] = []

    class FakeRoot:
        def mainloop(self) -> None:
            events.append("mainloop")

    class FakeWindow:
        def __init__(self, root, session, open_online) -> None:
            pass

        def start(self) -> None:
            events.append("start")

    monkeypatch.setattr(tkinter, "Tk", FakeRoot)
    monkeypatch.setattr("opendofusdata.window_view.CaptureWindow", FakeWindow)
    session = FakeSession()
    assert module.show_window(session, lambda: None) == EXIT_OK
    assert events == ["start", "mainloop"] and session.stop_calls == 1


def test_open_online_prices_uses_the_saas_url(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(module.webbrowser, "open", opened.append)
    module.open_online_prices()
    assert opened == [module.SAAS_URL]


def test_window_command_resolves_the_server_then_shows_the_window(monkeypatch) -> None:
    shown: list[object] = []
    monkeypatch.setattr(module, "resolve_run_server", lambda arguments: None)
    monkeypatch.setattr(module, "show_window", lambda session, opener: shown.append(session) or EXIT_OK)
    arguments = argparse.Namespace(db="x.db", server="Brial", interface=None)
    assert module.window_command(arguments) == EXIT_OK
    assert shown[0].snapshot().server == "Brial"


def test_cli_imports_and_runs_without_tkinter() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", LAZY_TKINTER_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == EXIT_OK, result.stderr
