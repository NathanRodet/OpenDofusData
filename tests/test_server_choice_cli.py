"""CLI tests for the remembered server: first run, saved run, --choose-server, server command."""

import builtins
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from opendofusdata import cli, server_choice_commands
from opendofusdata.app_config import CONFIG_ENV_VAR
from opendofusdata.capture import PacketPipeline
from opendofusdata.storage import PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope
from tests.test_servers_commands import make_servers

MOMENT = datetime(2026, 11, 10, 10, 29, 17, tzinfo=timezone.utc)
SERVERS_FILE = Path("data") / "servers.csv"


def config_file() -> Path:
    return Path(os.environ[CONFIG_ENV_VAR])


def write_config(text: str) -> None:
    config_file().parent.mkdir(parents=True, exist_ok=True)
    config_file().write_text(text, encoding="utf-8")


def saved_server() -> object:
    return json.loads(config_file().read_text(encoding="utf-8")).get("server")


def run_cli(argv: list[str], capture=None) -> int:
    return cli.run(argv, capture or (lambda pipeline, interface: None), lambda: MOMENT)


@pytest.fixture
def interactive(monkeypatch):
    """Make the session interactive and feed scripted answers to input()."""
    answers: list[str] = []
    monkeypatch.setattr(server_choice_commands, "is_interactive", lambda: True)

    def fake_input(prompt: str = "") -> str:
        if not answers:
            raise EOFError
        return answers.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)
    return answers


def test_first_run_prompts_and_saves(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    interactive.append("Draconiros")
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert "Serveur enregistré : Draconiros (choisi)" in capsys.readouterr().out
    assert saved_server() == "Draconiros"


def test_second_run_is_silent_and_uses_saved(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    interactive.append("1")
    run_cli(["run", "--db", "p.db"])
    capsys.readouterr()
    assert run_cli(["run", "--db", "p.db"]) == 0
    output = capsys.readouterr().out
    assert "Serveur enregistré : Draconiros (mémorisé ; --choose-server pour changer)" in output
    assert "Classique" not in output


def test_choose_server_asks_again(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    interactive.extend(["Draconiros", "Hell Mina"])
    run_cli(["run", "--db", "p.db"])
    assert run_cli(["run", "--db", "p.db", "--choose-server"]) == 0
    assert "Serveur enregistré : Hell Mina (choisi)" in capsys.readouterr().out
    assert saved_server() == "Hell Mina"


def test_option_does_not_touch_config_or_prompt(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    write_config('{"server": "Zed", "version": 1}')
    interactive.append("1")
    assert run_cli(["run", "--db", "p.db", "--server", "hell mina"]) == 0
    assert "Serveur enregistré : Hell Mina (option)" in capsys.readouterr().out
    assert saved_server() == "Zed" and interactive == ["1"]


def test_non_interactive_without_config_is_unknown_and_not_saved(capsys) -> None:
    assert run_cli(["run", "--db", "p.db"]) == 0
    output = capsys.readouterr().out
    assert "Serveur enregistré : unknown" in output and "server --set" in output
    assert not config_file().exists()


def test_skipped_prompt_runs_as_unknown_and_saves_nothing(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    interactive.append("")
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert "Serveur enregistré : unknown" in capsys.readouterr().out
    assert not config_file().exists()


def test_corrupt_config_does_not_abort_and_is_backed_up_on_choice(interactive) -> None:
    make_servers(SERVERS_FILE)
    write_config("{broken")
    interactive.append("Zed")
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert saved_server() == "Zed"
    assert config_file().with_name("config.json.corrupt").read_text(encoding="utf-8") == "{broken"


def test_corrupt_config_non_interactive_continues_as_unknown(capsys) -> None:
    write_config("{broken")
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert "Serveur enregistré : unknown" in capsys.readouterr().out
    assert config_file().read_text(encoding="utf-8") == "{broken"


def test_unwritable_config_does_not_abort(interactive, capsys, monkeypatch) -> None:
    make_servers(SERVERS_FILE)
    interactive.append("Zed")

    def failing_save(path, config) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(server_choice_commands, "save_config", failing_save)
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert "Serveur enregistré : Zed (choisi)" in capsys.readouterr().out


def test_corrupt_servers_file_does_not_abort(interactive, capsys) -> None:
    SERVERS_FILE.parent.mkdir(parents=True)
    SERVERS_FILE.write_bytes(b"\xff\xfe\x00\x80")
    interactive.append("Kourial")
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert "Serveur enregistré : Kourial (choisi)" in capsys.readouterr().out


def test_captured_records_carry_the_saved_server(tmp_path: Path) -> None:
    write_config('{"server": "Brial", "version": 1}')
    database = tmp_path / "p.db"

    def capture(pipeline: PacketPipeline, interface: str | None) -> None:
        pipeline.on_envelope(lot_envelope(), FLOW_KEY)

    assert run_cli(["run", "--db", str(database)], capture) == 0
    store = PriceStore(str(database))
    try:
        assert {lot.server for lot in store.latest_prices(307)} == {"Brial"}
    finally:
        store.close()


def test_server_command_shows_nothing_then_set_then_show(capsys) -> None:
    assert run_cli(["server"]) == 0
    assert "Aucun serveur" in capsys.readouterr().out
    make_servers(SERVERS_FILE)
    assert run_cli(["server", "--set", "hell mina"]) == 0
    assert saved_server() == "Hell Mina"
    capsys.readouterr()
    assert run_cli(["server"]) == 0
    assert "Hell Mina" in capsys.readouterr().out


def test_server_set_unlisted_is_refused_and_nothing_is_saved(capsys) -> None:
    make_servers(SERVERS_FILE)
    assert run_cli(["server", "--set", "Inconnu"]) != 0
    error = capsys.readouterr().err
    assert "Inconnu" in error and "servers-update" in error
    assert not config_file().exists()


def test_server_set_uses_the_bundled_list_without_a_servers_file() -> None:
    assert run_cli(["server", "--set", "kourial"]) == 0
    assert saved_server() == "Kourial"


def test_first_run_without_servers_file_lists_the_bundled_servers(interactive, capsys) -> None:
    interactive.append("")
    assert run_cli(["run", "--db", "p.db"]) == 0
    output = capsys.readouterr().out
    assert sum(line.startswith("  ") and line.strip()[0].isdigit() for line in output.splitlines()) == 13
    assert "  1. Brial" in output and "Kourial" in output


def test_first_run_prompt_rejects_free_text_and_saves_nothing(interactive) -> None:
    interactive.extend(["Mon Serveur", "Mon Serveur", "Mon Serveur"])
    assert run_cli(["run", "--db", "p.db"]) == 0
    assert not config_file().exists()


def test_servers_file_rows_replace_the_bundled_list(interactive, capsys) -> None:
    make_servers(SERVERS_FILE)
    interactive.append("")
    run_cli(["run", "--db", "p.db"])
    output = capsys.readouterr().out
    assert "Zed" in output and "Kourial" not in output


def test_unlisted_remembered_server_warns_once_and_is_used(capsys) -> None:
    write_config('{"server": "Fantome", "version": 1}')
    assert run_cli(["run", "--db", "p.db"]) == 0
    output = capsys.readouterr().out
    assert output.count("absent de la liste") == 1
    assert "Serveur enregistré : Fantome (mémorisé" in output


def test_blank_option_is_ignored_with_one_warning(interactive, capsys) -> None:
    write_config('{"server": "Brial", "version": 1}')
    assert run_cli(["run", "--db", "p.db", "--server", "  "]) == 0
    output = capsys.readouterr().out
    assert output.count("--server vide ignoré") == 1
    assert "Serveur enregistré : Brial (mémorisé" in output


def test_ctrl_c_at_the_prompt_stops_cleanly_without_capture(monkeypatch, capsys) -> None:
    monkeypatch.setattr(server_choice_commands, "is_interactive", lambda: True)

    def interrupted(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupted)
    started: list[str] = []
    with pytest.raises(SystemExit) as stop:
        run_cli(["run", "--db", "p.db"], lambda pipeline, interface: started.append("x"))
    assert stop.value.code not in (0, None) and started == []
    assert "Interrompu, aucune capture lancée." in capsys.readouterr().out


def test_server_clear_removes_the_key_and_keeps_others() -> None:
    write_config('{"server": "Zed", "other": 1, "version": 1}')
    assert run_cli(["server", "--clear"]) == 0
    data = json.loads(config_file().read_text(encoding="utf-8"))
    assert "server" not in data and data["other"] == 1
    assert run_cli(["server", "--clear"]) == 0


def test_server_set_and_clear_are_exclusive() -> None:
    with pytest.raises(SystemExit):
        run_cli(["server", "--set", "X", "--clear"])


def test_server_set_write_failure_reports_error(capsys, monkeypatch) -> None:
    def failing_save(path, config) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(server_choice_commands, "save_config", failing_save)
    assert run_cli(["server", "--set", "Brial"]) != 0
    assert "read-only" in capsys.readouterr().err


def test_a_missing_console_is_not_interactive(monkeypatch) -> None:
    monkeypatch.setattr(server_choice_commands.sys, "stdin", None)
    monkeypatch.setattr(server_choice_commands.sys, "stdout", None)
    assert server_choice_commands.is_interactive() is False
