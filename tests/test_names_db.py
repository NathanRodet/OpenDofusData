"""names-import and names-gaps: reference data inside the database."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from opendofusdata import cli, names_db
from opendofusdata.item_names import ItemEntry
from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore

GAP_LISTING_LIMIT = 20


def run_cli(argv: list[str]) -> int:
    return cli.run(argv, lambda *args, **kwargs: 0)


def make_database(path: Path, item_ids: list[int]) -> Path:
    store = PriceStore(str(path))
    for item_id in item_ids:
        store.save_lot_price(LotPrice(item_id, "S", 1, 10, "2026-11-01T00:00:00Z"))
        store.save_lot_price(LotPrice(item_id, "S", 10, 90, "2026-11-02T00:00:00Z"))
    store.close()
    return path


def make_names(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(["id,name_fr,level,type_fr", *rows]) + "\n", encoding="utf-8")
    return path


def items_of(path: Path) -> list[tuple]:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT * FROM items ORDER BY item_id").fetchall()


def do_import(database: Path, names: Path) -> int:
    return run_cli(["names-import", "--db", str(database), "--names", str(names)])


def test_import_fills_items_and_prints_the_summary(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1, 2])
    names = make_names(tmp_path / "items.csv", ["1,Un,5,Type", "3,Trois,,"])
    assert do_import(database, names) == 0
    assert items_of(database) == [(1, "Un", 5, "Type"), (3, "Trois", None, "")]
    output = capsys.readouterr().out
    assert "2 objets importés" in output and "1 identifiant" in output and "2 (2 relevés)" in output


def test_import_is_idempotent(tmp_path: Path) -> None:
    database = make_database(tmp_path / "p.db", [1])
    names = make_names(tmp_path / "items.csv", ["1,Un,5,Type", "2,Deux,6,Type"])
    do_import(database, names)
    first = items_of(database)
    assert do_import(database, names) == 0
    assert items_of(database) == first


def test_second_import_replaces_the_content(tmp_path: Path) -> None:
    database = make_database(tmp_path / "p.db", [1])
    do_import(database, make_names(tmp_path / "a.csv", ["1,Un,5,T", "2,Deux,6,T"]))
    do_import(database, make_names(tmp_path / "b.csv", ["1,Uno,5,T"]))
    assert items_of(database) == [(1, "Uno", 5, "T")]


def test_failing_row_rolls_back_and_leaves_items_unchanged(tmp_path: Path) -> None:
    database = make_database(tmp_path / "p.db", [1])
    do_import(database, make_names(tmp_path / "a.csv", ["1,Un,5,T", "2,Deux,6,T"]))

    def failing() -> Iterator[ItemEntry]:
        yield ItemEntry(9, "Neuf", 1, "T")
        raise RuntimeError("panne injectée")

    with closing(sqlite3.connect(database)) as connection:
        with pytest.raises(RuntimeError):
            names_db.replace_items(connection, failing())
    assert items_of(database) == [(1, "Un", 5, "T"), (2, "Deux", 6, "T")]


def test_missing_database_is_not_created(tmp_path: Path, capsys) -> None:
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    assert do_import(tmp_path / "absent.db", names) != 0
    assert not (tmp_path / "absent.db").exists()
    assert "introuvable" in capsys.readouterr().err


@pytest.mark.parametrize("rows", [None, []])
def test_missing_or_empty_names_file_leaves_the_database_untouched(tmp_path: Path, capsys, rows) -> None:
    database = tmp_path / "old.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE lot_prices (item_id INTEGER)")
    names = tmp_path / "items.csv" if rows is None else make_names(tmp_path / "items.csv", rows)
    before = database.read_bytes()
    assert do_import(database, names) != 0
    assert "names-update" in capsys.readouterr().err
    assert database.read_bytes() == before


def test_gap_listing_is_capped_at_twenty(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", list(range(100, 125)))
    do_import(database, make_names(tmp_path / "items.csv", ["1,Un,5,T"]))
    output = capsys.readouterr().out
    assert "25 identifiant" in output and "100 (2 relevés)" in output
    assert "119 (2 relevés)" in output and "120 (2 relevés)" not in output


def test_non_database_file_gives_the_french_error(tmp_path: Path, capsys) -> None:
    garbage = tmp_path / "garbage.db"
    garbage.write_text("not a database " * 50, encoding="utf-8")
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    assert do_import(garbage, names) != 0
    assert run_cli(["names-gaps", "--db", str(garbage)]) != 0
    assert capsys.readouterr().err.count("Base de données illisible") == 2


def test_gaps_table_lists_unknown_items(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1, 2])
    do_import(database, make_names(tmp_path / "items.csv", ["1,Un,5,T"]))
    capsys.readouterr()
    assert run_cli(["names-gaps", "--db", str(database)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split("  ")[0] == "id" and "relevés lots" in lines[0] and "dernier relevé" in lines[0]
    assert lines[1].split() == ["2", "2", "0", "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"]


def test_gaps_says_so_when_there_is_none(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1])
    do_import(database, make_names(tmp_path / "items.csv", ["1,Un,5,T"]))
    capsys.readouterr()
    assert run_cli(["names-gaps", "--db", str(database)]) == 0
    assert "Aucun identifiant sans nom" in capsys.readouterr().out


def test_gaps_hints_at_names_import_when_items_is_empty(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1])
    assert run_cli(["names-gaps", "--db", str(database)]) == 0
    output = capsys.readouterr().out
    assert "names-import" in output and "relevés lots" not in output


def test_gaps_on_a_missing_database_creates_nothing(tmp_path: Path, capsys) -> None:
    assert run_cli(["names-gaps", "--db", str(tmp_path / "absent.db")]) != 0
    assert not (tmp_path / "absent.db").exists()


def test_defaults_are_the_standard_paths() -> None:
    arguments = cli.build_parser().parse_args(["names-import"])
    assert (arguments.db, arguments.names) == ("prices.db", "data/items.csv")
    assert cli.build_parser().parse_args(["names-gaps"]).db == "prices.db"


@pytest.mark.parametrize("argv", [["prices"], ["history", "1", "--lot", "1"], ["stats", "1"],
                                  ["export-csv", "--output", "out.csv"], ["names-gaps"],
                                  ["names-import"]])
def test_empty_file_is_rejected_and_left_untouched(tmp_path: Path, capsys, argv: list[str]) -> None:
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    extra = ["--names", str(names)] if argv[0] == "names-import" else []
    if argv[0] == "export-csv":
        argv = [*argv[:2], str(tmp_path / "out.csv")]
    assert run_cli([*argv, "--db", str(empty), *extra]) != 0
    assert "est vide, pas une base de données" in capsys.readouterr().err
    assert empty.stat().st_size == 0
