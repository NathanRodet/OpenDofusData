"""CLI tests for names-update (download through an injected fetch)."""

from pathlib import Path

from dofus_prices import cli, names_commands
from dofus_prices.names_build import NamesFetchError
from tests.test_names_fetch import FakeApi


def parse_update(argv: list[str]):
    return cli.build_parser().parse_args(["names-update", *argv])


def test_names_update_downloads_through_the_injected_fetch(tmp_path: Path, capsys) -> None:
    output = tmp_path / "out" / "items.csv"
    arguments = parse_update(["--output", str(output)])
    assert names_commands.names_update_command(arguments, fetch=FakeApi(), request_delay=0.0,
                                               sleep=lambda seconds: None) == 0
    text = capsys.readouterr().out
    assert text.index("api.dofusdb.fr") < text.index(str(output))
    assert "hors ligne" in text and "4 objets" in text and "1 ignoré" in text
    assert output.is_file()


def test_names_update_reports_a_failure_in_french(tmp_path: Path, capsys) -> None:
    def broken(url: str) -> object:
        raise NamesFetchError("Téléchargement impossible : test.")

    arguments = parse_update(["--output", str(tmp_path / "items.csv")])
    assert names_commands.names_update_command(arguments, fetch=broken, request_delay=0.0,
                                               sleep=lambda seconds: None) != 0
    assert "Téléchargement impossible : test." in capsys.readouterr().err
    assert not (tmp_path / "items.csv").exists()


def test_names_update_default_output_is_data_items_csv() -> None:
    assert parse_update([]).output == "data/items.csv"
