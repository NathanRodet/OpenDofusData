"""Tests of the executable launcher: default command and file logging (no GUI started)."""

import logging

from opendofusdata import launcher
from opendofusdata.launcher import arguments_for, configure_file_logging, log_file_path


def test_no_argument_opens_the_window() -> None:
    assert arguments_for([]) == ["window"]


def test_explicit_arguments_are_left_alone() -> None:
    assert arguments_for(["prices", "--item", "307"]) == ["prices", "--item", "307"]
    assert arguments_for(["window", "--server", "Brial"]) == ["window", "--server", "Brial"]


def test_the_log_file_lives_next_to_the_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(tmp_path / "cfg" / "config.json"))
    assert log_file_path() == tmp_path / "cfg" / "opendofusdata.log"


def test_file_logging_writes_messages_and_is_installed_once(tmp_path) -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        path = tmp_path / "logs" / "app.log"
        configure_file_logging(path)
        configure_file_logging(path)
        added = [handler for handler in root.handlers if handler not in before]
        assert len(added) == 1
        logging.getLogger("test-launcher").warning("bonjour le journal")
        added[0].flush()
        assert "bonjour le journal" in path.read_text(encoding="utf-8")
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()


def test_main_runs_the_cli_with_the_default_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENDOFUSDATA_CONFIG", str(tmp_path / "config.json"))
    seen: list[list[str]] = []
    monkeypatch.setattr(launcher, "configure_file_logging", lambda path: None)
    monkeypatch.setattr(launcher.cli, "main", lambda argv: seen.append(argv) or 0)
    assert launcher.main([]) == 0
    assert seen == [["window"]]
