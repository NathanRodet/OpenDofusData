"""Tests for the window command wiring (no real display needed)."""

import argparse
import subprocess
import sys
import threading
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
    return module.WindowContext(session, Path("config.json"), [], lambda item_id: "N/A")


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


def test_cli_imports_and_runs_without_tkinter() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", LAZY_TKINTER_SCRIPT, str(SOURCE_DIRECTORY)],
        capture_output=True, text=True)
    assert result.returncode == EXIT_OK, result.stderr


class FakeWorker:
    """Stands in for the sync worker: records its life cycle."""

    instances: list["FakeWorker"] = []

    def __init__(self, database_path, load_options) -> None:
        self.database_path, self.load_options = database_path, load_options
        self.events: list[str] = []
        FakeWorker.instances.append(self)

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")

    def status(self) -> str:
        return "Synchronisation terminée"


def test_window_command_runs_the_sync_worker_around_the_window(monkeypatch, tmp_path) -> None:
    FakeWorker.instances.clear()
    monkeypatch.setattr(module, "SyncWorker", FakeWorker)
    context = run_window_command(monkeypatch, tmp_path, "x.db", None)
    worker = FakeWorker.instances[0]
    assert worker.events == ["start", "stop"]
    assert worker.database_path() == "x.db"
    assert context.sync_status() == "Synchronisation terminée"
    assert worker.load_options() is None  # nothing is switched on by default


def test_the_sync_worker_is_stopped_even_if_the_window_fails(monkeypatch, tmp_path) -> None:
    FakeWorker.instances.clear()
    monkeypatch.setattr(module, "SyncWorker", FakeWorker)
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setattr(module, "resolve_run_server", lambda arguments: None)

    def crash(context) -> int:
        raise RuntimeError("window failed")

    monkeypatch.setattr(module, "show_window", crash)
    try:
        module.window_command(argparse.Namespace(db="x.db", server="Brial", interface=None))
    except RuntimeError:
        pass
    assert FakeWorker.instances[0].events == ["start", "stop"]


def test_the_startup_purge_gets_the_config_and_the_database(monkeypatch, tmp_path) -> None:
    done = threading.Event()
    calls: list[tuple] = []
    monkeypatch.setattr(module, "SyncWorker", FakeWorker)
    monkeypatch.setattr(module, "startup_purge", lambda config, database: calls.append((config, database)) or done.set())
    run_window_command(monkeypatch, tmp_path, "x.db", '{"purge_old_data": true}')
    assert done.wait(5)
    assert calls[0][1] == "x.db" and calls[0][0]["purge_old_data"] is True
