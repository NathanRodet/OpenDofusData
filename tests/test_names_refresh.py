"""Tests of the reference-data refresh used by the window (fake API, temp database)."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from opendofusdata.names_fetch import NamesFetchError
from opendofusdata.names_refresh import loaded_item_count, refresh_reference_data
from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore
from tests.test_names_fetch import FakeApi

ITEM_TYPES = [{"id": 1, "name": {"fr": "Ressource"}}]
ITEMS = [
    {"id": 307, "typeId": 1, "level": 1, "name": {"fr": "Ailes de Moskito"}},
    {"id": 376, "typeId": 1, "level": 20, "name": {"fr": "Aile du Tofu Maléfique"}},
]
GAME_TYPES = [{"id": 0, "name": {"fr": "Classique"}}]
SERVERS = [{"id": 293, "name": {"fr": "Tylezia"}, "gameTypeId": 0, "communityId": 2}]


class FakeDofusDb(FakeApi):
    """Serves the four collections the refresh downloads."""

    def __init__(self) -> None:
        super().__init__()
        self._collections = {"/items": ITEMS, "/item-types": ITEM_TYPES,
                             "/servers": SERVERS, "/server-game-types": GAME_TYPES}


def refresh(tmp_path: Path, fetch=None):
    return refresh_reference_data(str(tmp_path / "p.db"), tmp_path / "ref", fetch or FakeDofusDb(),
                                  request_delay=0.0, sleep=lambda seconds: None)


def test_refresh_fills_items_and_servers_and_reports_counts(tmp_path) -> None:
    result = refresh(tmp_path)
    assert (result.items, result.servers) == (2, 1)
    with closing(sqlite3.connect(tmp_path / "p.db")) as connection:
        assert connection.execute("SELECT name_fr FROM items WHERE item_id = 307").fetchone() == ("Ailes de Moskito",)
        assert connection.execute("SELECT name_fr FROM servers").fetchall() == [("Tylezia",)]


def test_refresh_creates_the_data_directory_and_keeps_the_csv_files(tmp_path) -> None:
    refresh(tmp_path)
    assert (tmp_path / "ref" / "items.csv").is_file()
    assert (tmp_path / "ref" / "servers.csv").is_file()


def test_refresh_keeps_the_captured_prices(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "p.db"))
    store.save_lot_price(LotPrice(307, "Brial", 1, 750, "2026-11-11T10:00:00Z"))
    store.close()
    refresh(tmp_path)
    store = PriceStore(str(tmp_path / "p.db"))
    try:
        assert len(store.latest_prices()) == 1
    finally:
        store.close()


def test_a_failing_download_raises_and_leaves_the_database_names_untouched(tmp_path) -> None:
    refresh(tmp_path)
    broken = FakeDofusDb()
    broken.failures = [NamesFetchError("API indisponible")] * 10
    with pytest.raises(NamesFetchError):
        refresh(tmp_path, broken)
    assert loaded_item_count(str(tmp_path / "p.db")) == 2


def test_loaded_item_count_is_zero_for_a_missing_database_and_never_creates_it(tmp_path) -> None:
    assert loaded_item_count(str(tmp_path / "absent.db")) == 0
    assert not (tmp_path / "absent.db").exists()


def test_loaded_item_count_is_zero_for_a_database_without_names(tmp_path) -> None:
    PriceStore(str(tmp_path / "p.db")).close()
    assert loaded_item_count(str(tmp_path / "p.db")) == 0


def test_loaded_item_count_is_zero_for_a_corrupt_file(tmp_path) -> None:
    (tmp_path / "bad.db").write_bytes(b"not a database" * 100)
    assert loaded_item_count(str(tmp_path / "bad.db")) == 0
