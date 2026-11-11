"""Tests for the window command wiring (no real display needed)."""

import argparse
import subprocess
import sys
import tkinter
from pathlib import Path

import customtkinter

from opendofusdata import window_command as module
from opendofusdata.capture_errors import EXIT_FAILED, EXIT_OK

SOURCE_DIRECTORY = Path(__file__).resolve().parent.parent / "src"
LAZY_TKINTER_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); sys.modules['tkinter'] = None; "
    "import opendofusdata.cli as cli; "
    "sys.exit(cli.run(['prices', '--help'], lambda pipeline, interface: None))"
)


def make_context(session) -> module.WindowContext:
    return module.WindowContext(session, lambda: None, Path("config.json"), [], lambda item_id: "N/A")


class FakeSession:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


def test_no_display_gives_a_clear_failure(monkeypatch, capsys) -> None:
    def no_display() -> None:
        raise tkinter.TclError("no display name")

    monkeypatch.setattr(customtkinter, "CTk", no_display)
    assert module.show_window(make_context(FakeSession())) == EXIT_FAILED
    assert "no display name" in capsys.readouterr().err


def test_session_is_stopped_after_the_main_loop(monkeypatch) -> None:
    events: list[str] = []

    class FakeRoot:
        def mainloop(self) -> None:
            events.append("mainloop")

    class FakeWindow:
        def __init__(self, root, context) -> None:
            pass

        def start(self) -> None:
            events.append("start")

    monkeypatch.setattr(customtkinter, "CTk", FakeRoot)
    monkeypatch.setattr("opendofusdata.window_view.CaptureWindow", FakeWindow)
    session = FakeSession()
    assert module.show_window(make_context(session)) == EXIT_OK
    assert events == ["start", "mainloop"] and session.stop_calls == 1


def test_open_online_prices_uses_the_saas_url(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(module.webbrowser, "open", opened.append)
    module.open_online_prices()
    assert opened == [module.SAAS_URL]


def run_window_command(monkeypatch, tmp_path, db: str | None, config_text: str | None) -> module.WindowContext:
    shown: list[module.WindowContext] = []
    config_path = tmp_path / "config.json"
    if config_text is not None:
        config_path.write_text(config_text, encoding="utf-8")
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(config_path))
    monkeypatch.setattr(module, "resolve_run_server", lambda arguments: None)
    monkeypatch.setattr(module, "show_window", lambda context: shown.append(context) or EXIT_OK)
    arguments = argparse.Namespace(db=db, server="Brial", interface=None)
    assert module.window_command(arguments) == EXIT_OK
    return shown[0]


def test_window_command_resolves_the_server_then_shows_the_window(monkeypatch, tmp_path) -> None:
    context = run_window_command(monkeypatch, tmp_path, "x.db", None)
    assert context.session.snapshot().server == "Brial"
    assert context.config_path == tmp_path / "config.json"


def test_database_option_beats_the_saved_path(monkeypatch, tmp_path) -> None:
    context = run_window_command(monkeypatch, tmp_path, "cli.db", '{"database_path": "saved.db"}')
    assert context.session.database_path == "cli.db"


def test_saved_database_path_is_used_without_the_option(monkeypatch, tmp_path) -> None:
    context = run_window_command(monkeypatch, tmp_path, None, '{"database_path": "saved.db"}')
    assert context.session.database_path == "saved.db"


def test_default_database_when_nothing_is_set(monkeypatch, tmp_path) -> None:
    context = run_window_command(monkeypatch, tmp_path, None, "{ corrupt")
    assert context.session.database_path == "prices.db"


def test_saved_categories_are_loaded(monkeypatch, tmp_path) -> None:
    context = run_window_command(monkeypatch, tmp_path, None, '{"enabled_categories": []}')
    assert context.session.categories.enabled_keys() == []


def test_cli_imports_and_runs_without_tkinter() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", LAZY_TKINTER_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == EXIT_OK, result.stderr
