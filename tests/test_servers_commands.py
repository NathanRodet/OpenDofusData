"""CLI tests for servers-update, servers and the --server normalisation."""

import re
from pathlib import Path

import pytest

from dofus_prices import cli, servers_commands
from dofus_prices.names_build import NamesFetchError
from tests.test_servers_fetch import FakeServersApi

HEADER = "id,name_fr,game_type_id,game_type_fr,community_id\n"


def run_cli(argv: list[str]) -> int:
    return cli.run(argv, lambda *args, **kwargs: 0)


def make_servers(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "295,Draconiros,0,Classique,0\n900,Speed Rush,3,Tournoi,1\n"
                    "294,Hell Mina,0,Classique,0\n9,Zed,77,,1\n", encoding="utf-8")
    return path


def update(argv: list[str], fetch) -> int:
    arguments = cli.build_parser().parse_args(["servers-update", *argv])
    return servers_commands.servers_update_command(
        arguments, fetch=fetch, request_delay=0.0, sleep=lambda seconds: None)


def test_update_downloads_and_summarises(tmp_path: Path, capsys) -> None:
    output = tmp_path / "out" / "servers.csv"
    assert update(["--output", str(output)], FakeServersApi()) == 0
    text = capsys.readouterr().out
    assert text.index("api.dofusdb.fr") < text.index(str(output))
    assert "hors ligne" in text and "5 serveurs" in text and "1 ignoré" in text
    assert output.is_file()


def test_update_default_output_is_the_constant() -> None:
    arguments = cli.build_parser().parse_args(["servers-update"])
    assert arguments.output == "data/servers.csv"


def test_update_failure_and_interruption(tmp_path: Path, capsys) -> None:
    def broken(url: str) -> object:
        raise NamesFetchError("Téléchargement impossible : test.")

    def interrupted(url: str) -> object:
        raise KeyboardInterrupt

    assert update(["--output", str(tmp_path / "s.csv")], broken) != 0
    assert update(["--output", str(tmp_path / "s.csv")], interrupted) != 0
    err = capsys.readouterr().err
    assert "Téléchargement impossible : test." in err and "Interrompu, aucun fichier modifié." in err
    assert list(tmp_path.iterdir()) == []


def test_servers_prints_aligned_table_sorted_by_type_then_name(tmp_path: Path, capsys) -> None:
    path = make_servers(tmp_path / "servers.csv")
    assert run_cli(["servers", "--servers", str(path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "DofusDB" in lines[0] and "Dofus 3" in lines[0]
    assert lines[1].split() == ["id", "nom", "type"]
    names = [re.split(r"\s{2,}", line)[1] for line in lines[2:]]
    assert names == ["Zed", "Draconiros", "Hell Mina", "Speed Rush"]
    assert lines[3].startswith("295") and lines[3].rstrip().endswith("Classique")


@pytest.mark.parametrize("content", [None, HEADER])
def test_servers_without_data_gives_the_hint(tmp_path: Path, capsys, content) -> None:
    path = tmp_path / "servers.csv"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert run_cli(["servers", "--servers", str(path)]) == 0
    assert "servers-update" in capsys.readouterr().out


def test_servers_default_path() -> None:
    assert cli.build_parser().parse_args(["servers"]).servers == "data/servers.csv"


def test_known_server_gets_the_canonical_spelling(tmp_path: Path, capsys) -> None:
    path = make_servers(tmp_path / "servers.csv")
    assert servers_commands.resolve_server_name("draconiros", str(path)) == "Draconiros"
    assert capsys.readouterr().out == ""


def test_unknown_server_warns_once_and_is_kept(tmp_path: Path, capsys) -> None:
    path = make_servers(tmp_path / "servers.csv")
    assert servers_commands.resolve_server_name("Inconnu", str(path)) == "Inconnu"
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["serveur « Inconnu » absent de la liste (servers-update pour la mettre à jour)"]


def test_default_name_and_missing_file_stay_silent(tmp_path: Path, capsys) -> None:
    path = make_servers(tmp_path / "servers.csv")
    assert servers_commands.resolve_server_name("unknown", str(path)) == "unknown"
    assert servers_commands.resolve_server_name("X", str(tmp_path / "absent.csv")) == "X"
    assert capsys.readouterr().out == ""


def test_run_command_stores_the_canonical_name(tmp_path: Path, monkeypatch) -> None:
    make_servers(tmp_path / "data" / "servers.csv")
    monkeypatch.chdir(tmp_path)
    seen: list[str] = []

    def fake_run_command(arguments, capture, now) -> int:
        seen.append(arguments.server)
        return 0

    monkeypatch.setattr(cli, "run_command", fake_run_command)
    assert run_cli(["run", "--server", "hell mina"]) == 0
    assert seen == ["Hell Mina"]
