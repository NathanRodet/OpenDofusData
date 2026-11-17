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
    {"id": 376, "typeId": 1, "level": 20, "name": {"fr": "Aile du Tofu Maléfique"},
     "possibleEffects": [{"actionId": 125, "diceNum": 5, "diceSide": 8}]},
]
RECIPES = [{"resultId": 376, "ingredientIds": [307], "quantities": [4]}]
EFFECTS = [{"id": 125, "effectPowerRate": 0.5}]
GAME_TYPES = [{"id": 0, "name": {"fr": "Classique"}}]
SERVERS = [{"id": 293, "name": {"fr": "Tylezia"}, "gameTypeId": 0, "communityId": 2}]


class FakeDofusDb(FakeApi):
    """Serves the six collections the refresh downloads."""

    def __init__(self) -> None:
        super().__init__()
        self._collections = {"/items": ITEMS, "/item-types": ITEM_TYPES,
                             "/servers": SERVERS, "/server-game-types": GAME_TYPES,
                             "/recipes": RECIPES, "/effects": EFFECTS}


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


def test_refresh_also_downloads_recipes_and_effects_and_reports_counts(tmp_path) -> None:
    result = refresh(tmp_path)
    assert (result.recipes, result.effects) == (1, 1)
    for name in ("recipes.csv", "item_effects.csv", "runes.csv"):
        assert (tmp_path / "ref" / name).is_file()


def test_a_failing_recipes_download_raises_after_the_names_are_loaded(tmp_path) -> None:
    api = FakeDofusDb()

    def fetch(url: str) -> object:
        if "/recipes" in url:
            raise NamesFetchError("API indisponible")
        return api(url)

    with pytest.raises(NamesFetchError):
        refresh(tmp_path, fetch)
    assert loaded_item_count(str(tmp_path / "p.db")) == 2


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


def test_reference_data_is_missing_when_names_recipes_or_effects_are_absent(tmp_path) -> None:
    from opendofusdata.names_refresh import reference_data_missing

    database = str(tmp_path / "prices.db")
    assert reference_data_missing(database, tmp_path) is True  # nothing at all
    store = PriceStore(database)
    with store.connection:
        store.connection.execute("INSERT INTO items (item_id, name_fr) VALUES (1, 'A')")
    (tmp_path / "recipes.csv").write_text("x", encoding="utf-8")
    assert reference_data_missing(database, tmp_path) is True  # no effects file yet
    (tmp_path / "item_effects.csv").write_text("x", encoding="utf-8")
    assert reference_data_missing(database, tmp_path) is False


def test_the_card_call_gives_the_progress_callback_as_progress_not_as_the_fetch_function() -> None:
    """Regression (2.2.2 and 2.2.3): the callback landed in `fetch`, so every answer was None."""
    import inspect

    from opendofusdata.names_fetch import http_get_json
    from opendofusdata.names_refresh import refresh_reference_data

    def callback(message: str) -> None:
        return None

    bound = inspect.signature(refresh_reference_data).bind("prices.db", Path("data"), progress=callback)
    bound.apply_defaults()
    assert bound.arguments["fetch"] is http_get_json and bound.arguments["progress"] is callback
