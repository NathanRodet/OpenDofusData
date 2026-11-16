"""Tests of the reset of the collected data and of its command."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from opendofusdata import cli
from opendofusdata.records import BrokenItem, LotPrice, MarketStats, PetFeeding, PetState
from opendofusdata.reset_data import COLLECTED_TABLES, reset_collected_data
from opendofusdata.storage import PriceStore

NOW = datetime(2026, 11, 13, 1, 2, 3, tzinfo=timezone.utc)


def fill(path: str) -> None:
    store = PriceStore(path)
    stamp = "2026-11-12T10:00:00Z"
    store.save_lot_price(LotPrice(7, "Brial", 1, 100, stamp))
    store.save_market_stats(MarketStats(7, "Brial", "24h", [], 1, 1, 1, stamp, stamp, stamp))
    store.save_record(BrokenItem("Brial", 7, 1, 0.5, ((1, 2),), stamp))
    store.save_record(PetFeeding("Brial", 9, ((7, 1),), PetState(1, 0, 9, 0), PetState(1, 2, 9, 0), stamp))
    store.connection.execute("INSERT INTO items (item_id, name_fr, level, type_fr, recycling_nuggets) "
                             "VALUES (7, 'Objet', 1, 'Ressource', 0)")
    store.connection.commit()
    store.close()


def count(path, table: str) -> int:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_reset_empties_collected_tables_and_keeps_names(tmp_path) -> None:
    path = str(tmp_path / "p.db")
    fill(path)
    reset_collected_data(path, NOW)
    assert [count(path, table) for table in COLLECTED_TABLES] == [0, 0, 0, 0]
    assert count(path, "items") == 1


def test_reset_writes_a_backup_with_the_old_rows(tmp_path) -> None:
    path = str(tmp_path / "p.db")
    fill(path)
    backup = reset_collected_data(path, NOW)
    assert backup.name == "p-backup-20261113-010203.db"
    assert [count(backup, table) for table in COLLECTED_TABLES] == [1, 1, 1, 1]


def test_reset_of_a_missing_database_fails_clearly(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="introuvable"):
        reset_collected_data(str(tmp_path / "absent.db"), NOW)


def test_cli_refuses_without_yes_and_changes_nothing(tmp_path, capsys) -> None:
    path = str(tmp_path / "p.db")
    fill(path)
    assert cli.run(["reset-data", "--db", path], lambda *args: 0) != 0
    assert "--yes" in capsys.readouterr().out
    assert count(path, "lot_prices") == 1
    assert list(tmp_path.glob("*backup*")) == []


def test_cli_with_yes_resets_and_reports_the_backup(tmp_path, capsys) -> None:
    path = str(tmp_path / "p.db")
    fill(path)
    assert cli.run(["reset-data", "--db", path, "--yes"], lambda *args: 0) == 0
    assert "Sauvegarde" in capsys.readouterr().out
    assert count(path, "lot_prices") == 0 and len(list(tmp_path.glob("*backup*"))) == 1


def test_reset_also_forgets_the_sync_position(tmp_path) -> None:
    path = str(tmp_path / "prices.db")
    fill(path)
    store = PriceStore(path)
    from opendofusdata.sync_store import get_state, set_state
    set_state(store.connection, "cursor", "42")
    set_state(store.connection, "latest_done", "1")
    store.close()
    reset_collected_data(path, NOW)
    store = PriceStore(path)
    assert get_state(store.connection, "cursor") is None
    assert get_state(store.connection, "latest_done") is None
    store.close()
