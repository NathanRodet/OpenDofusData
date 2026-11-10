"""names-import also loads servers.csv, in the same transaction as items."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from dofus_prices import cli, names_db
from dofus_prices.game_servers import GameServer
from dofus_prices.item_names import ItemEntry
from tests.test_names_db import do_import, items_of, make_database, make_names
from tests.test_servers_commands import make_servers

NO_SERVERS = "absent-servers.csv"
SHORT_SERVERS = "id,name_fr,game_type_id,game_type_fr,community_id\n1,Un,0,C,0\n"


def servers_of(path: Path) -> list[tuple]:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT * FROM servers ORDER BY server_id").fetchall()


def import_both(database: Path, names: Path, servers: Path) -> int:
    return cli.run(["names-import", "--db", str(database), "--names", str(names),
                    "--servers", str(servers)], lambda *args, **kwargs: 0)


def seeded(tmp_path: Path) -> tuple[Path, Path, tuple]:
    database = make_database(tmp_path / "p.db", [1])
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    import_both(database, names, make_servers(tmp_path / "servers.csv"))
    return database, names, (items_of(database), servers_of(database))


def test_both_tables_are_imported_with_a_summary(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1])
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    assert import_both(database, names, make_servers(tmp_path / "servers.csv")) == 0
    assert items_of(database) == [(1, "Un", 5, "T")]
    assert servers_of(database)[0] == (9, "Zed", 77, "", 1)
    assert len(servers_of(database)) == 4
    assert "4 serveurs importés" in capsys.readouterr().out


def test_missing_servers_file_imports_items_only_with_a_note(tmp_path: Path, capsys) -> None:
    database = make_database(tmp_path / "p.db", [1])
    names = make_names(tmp_path / "items.csv", ["1,Un,5,T"])
    assert import_both(database, names, tmp_path / NO_SERVERS) == 0
    output = capsys.readouterr().out
    assert items_of(database) == [(1, "Un", 5, "T")] and servers_of(database) == []
    assert "servers-update" in output and "1 objets importés" in output


def test_servers_are_replaced_not_merged(tmp_path: Path) -> None:
    database, names, _ = seeded(tmp_path)
    short = tmp_path / "short.csv"
    short.write_text(SHORT_SERVERS, encoding="utf-8")
    import_both(database, names, short)
    assert servers_of(database) == [(1, "Un", 0, "C", 0)]


def test_failure_in_servers_rolls_back_items_and_servers(tmp_path: Path) -> None:
    database, _, before = seeded(tmp_path)

    def failing() -> Iterator[GameServer]:
        yield GameServer(1, "Nouveau", 0, "C", 0)
        raise RuntimeError("panne injectée")

    with closing(sqlite3.connect(database)) as connection:
        with pytest.raises(RuntimeError):
            names_db.replace_items(connection, [ItemEntry(9, "Neuf", 1, "T")], failing())
    assert (items_of(database), servers_of(database)) == before


def test_failure_in_items_rolls_back_servers_too(tmp_path: Path) -> None:
    database, _, before = seeded(tmp_path)

    def failing() -> Iterator[ItemEntry]:
        yield ItemEntry(9, "Neuf", 1, "T")
        raise RuntimeError("panne injectée")

    with closing(sqlite3.connect(database)) as connection:
        with pytest.raises(RuntimeError):
            names_db.replace_items(connection, failing(), [GameServer(1, "N", 0, "C", 0)])
    assert (items_of(database), servers_of(database)) == before


def test_old_database_gains_the_servers_table(tmp_path: Path) -> None:
    old = make_database(tmp_path / "old.db", [1])
    with closing(sqlite3.connect(old)) as connection:
        connection.execute("DROP TABLE servers")
    do_import(old, make_names(tmp_path / "items.csv", ["1,Un,5,T"]))
    assert servers_of(old) == []
