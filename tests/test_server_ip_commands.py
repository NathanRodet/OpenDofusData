"""Tests for server --learn / --ips / --forget (injected netstat runner, no subprocess)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from dofus_prices import cli, server_ip_commands
from dofus_prices.app_config import CONFIG_ENV_VAR

KOURIAL_IP = "99.81.217.174"
OTHER_IP = "52.17.4.9"
PLAYER_IP = "192.168.1.20"
NETSTAT_OUTPUT = f"""
  Proto  Local Address          Foreign Address        State
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING
  TCP    {PLAYER_IP}:49822     {OTHER_IP}:5555     ESTABLISHED
  TCP    {PLAYER_IP}:49823     127.0.0.1:5555      ESTABLISHED
  TCP    {PLAYER_IP}:49824     {OTHER_IP}:443      TIME_WAIT
"""
NO_GAME_OUTPUT = f"  TCP    {PLAYER_IP}:49830     {OTHER_IP}:443     ESTABLISHED\n"


def config_path() -> Path:
    return Path(os.environ[CONFIG_ENV_VAR])


def write_config(document: dict) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(document), encoding="utf-8")


def saved_config() -> dict:
    return json.loads(config_path().read_text(encoding="utf-8"))


def learn(argv: list[str], netstat) -> int:
    arguments = cli.build_parser().parse_args(["server", *argv])
    return server_ip_commands.learn_command(arguments, netstat)


def test_learn_maps_the_game_connection_to_the_name_and_saves(capsys) -> None:
    assert learn(["--learn", "Brial"], lambda: NETSTAT_OUTPUT) == 0
    assert saved_config()["ips"] == {OTHER_IP: "Brial"}
    output = capsys.readouterr().out
    assert f"adresse du serveur de jeu {OTHER_IP} associée à « Brial »" in output
    assert PLAYER_IP not in output and "127.0.0.1" not in output and PLAYER_IP not in str(saved_config())


def test_learn_without_name_uses_the_remembered_server() -> None:
    write_config({"server": "Draconiros"})
    assert learn(["--learn"], lambda: NETSTAT_OUTPUT) == 0
    assert saved_config()["ips"] == {OTHER_IP: "Draconiros"} and saved_config()["server"] == "Draconiros"


def test_learn_without_name_nor_remembered_server_is_an_error(capsys) -> None:
    assert learn(["--learn"], lambda: NETSTAT_OUTPUT) != 0
    assert "Aucun serveur mémorisé" in capsys.readouterr().err
    assert not config_path().exists()


@pytest.mark.parametrize("name", ["   ", "unknown"])
def test_learn_refuses_a_bad_name(name: str, capsys) -> None:
    assert learn(["--learn", name], lambda: NETSTAT_OUTPUT) != 0
    assert capsys.readouterr().err != "" and not config_path().exists()


def test_learn_with_no_game_connection_says_so(capsys) -> None:
    assert learn(["--learn", "Brial"], lambda: NO_GAME_OUTPUT) != 0
    assert "aucune connexion de jeu active : lance le jeu et connecte-toi" in capsys.readouterr().err
    assert not config_path().exists()


@pytest.mark.parametrize("error", [OSError("introuvable"), subprocess.TimeoutExpired("netstat", 10),
                                   subprocess.CalledProcessError(1, "netstat")])
def test_learn_reports_a_netstat_failure(error: Exception, capsys) -> None:
    def failing() -> str:
        raise error

    assert learn(["--learn", "Brial"], failing) != 0
    assert "netstat" in capsys.readouterr().err and not config_path().exists()


def test_learn_keeps_other_config_keys_and_reports_a_write_failure(monkeypatch, capsys) -> None:
    write_config({"server": "Zed", "other": 1})
    learn(["--learn", "Brial"], lambda: NETSTAT_OUTPUT)
    assert saved_config()["other"] == 1 and saved_config()["server"] == "Zed"

    def failing_save(path, config) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(server_ip_commands, "save_config", failing_save)
    assert learn(["--learn", "Brial"], lambda: NETSTAT_OUTPUT) != 0
    assert "Impossible d'écrire" in capsys.readouterr().err


def test_netstat_runner_uses_a_fixed_argument_list_without_shell(monkeypatch) -> None:
    seen: dict = {}

    def fake_run(command, **options):
        seen.update(command=command, options=options)
        return subprocess.CompletedProcess(command, 0, stdout=b"  TCP a b c\n", stderr=b"")

    monkeypatch.setattr(server_ip_commands.subprocess, "run", fake_run)
    assert server_ip_commands.run_netstat() == "  TCP a b c\n"
    assert seen["command"] == ["netstat", "-n", "-p", "tcp"]
    assert seen["options"]["capture_output"] is True and seen["options"]["timeout"] > 0
    assert not seen["options"].get("shell")


def test_ips_lists_bundled_and_learned_addresses(capsys) -> None:
    write_config({"ips": {OTHER_IP: "Brial"}})
    assert cli.run(["server", "--ips"], lambda *args: None) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["adresse", "serveur", "origine"]
    assert lines[1].split() == [OTHER_IP, "Brial", "appris"]
    assert lines[2].split() == [KOURIAL_IP, "Kourial", "livré"]


def test_forget_removes_a_learned_address_and_keeps_the_rest(capsys) -> None:
    write_config({"server": "Zed", "ips": {OTHER_IP: "Brial", "52.17.4.10": "Dakal"}})
    assert cli.run(["server", "--forget", OTHER_IP], lambda *args: None) == 0
    assert saved_config()["ips"] == {"52.17.4.10": "Dakal"} and saved_config()["server"] == "Zed"
    assert "oubliée" in capsys.readouterr().out


def test_forget_of_a_bundled_or_unknown_or_invalid_address_changes_nothing(capsys) -> None:
    write_config({"ips": {OTHER_IP: "Brial"}})
    before = config_path().read_text(encoding="utf-8")
    for address in (KOURIAL_IP, "52.17.4.99", PLAYER_IP, "garbage"):
        assert cli.run(["server", "--forget", address], lambda *args: None) != 0
    assert config_path().read_text(encoding="utf-8") == before
    assert PLAYER_IP not in capsys.readouterr().err


def test_learn_ips_forget_set_and_clear_are_exclusive() -> None:
    for extra in (["--ips"], ["--forget", OTHER_IP], ["--set", "X"], ["--clear"]):
        with pytest.raises(SystemExit):
            cli.run(["server", "--learn", "Brial", *extra], lambda *args: None)
