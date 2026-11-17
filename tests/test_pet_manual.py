"""Experience typed by the player: storage, search, merge into the rows and the form."""

import pytest

from opendofusdata.item_search import search_items
from opendofusdata.pet_manual_form import parse_count
from opendofusdata.app_config import load_config, save_config
from opendofusdata.pet_manual_store import (
    PET_MANUAL_KEY, add_manual, import_config_manual, load_manual, own_manual, remove_manual,
)
from opendofusdata.pets_view_data import pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.records import LotPrice
from tests.view_page_helpers import open_store

BOUE = 1001
NAMES = {BOUE: "Boue du Boo"}
EVERYTHING = (None, None)


def test_typed_experience_is_added_up_and_can_be_removed(tmp_path) -> None:
    store = open_store(tmp_path)
    connection = store.connection
    assert add_manual(connection, BOUE, 10, 50) and add_manual(connection, BOUE, 5, 25)
    typed = load_manual(connection)[BOUE]
    assert (typed.units, typed.experience, typed.feedings) == (15, 75, 0)
    assert remove_manual(connection, BOUE) and load_manual(connection) == {}
    store.close()


def test_the_experience_typed_by_the_other_players_is_added_to_mine(tmp_path) -> None:
    store = open_store(tmp_path)
    connection = store.connection
    add_manual(connection, BOUE, 10, 50)
    insert = ("INSERT INTO pet_manual_entries (captured_at, item_id, units, experience, origin, synced_at, "
              "source_key_id) VALUES (?, ?, ?, ?, 'remote', '2026-11-17T10:00:00Z', ?)")
    connection.execute(insert, ("2026-11-17T09:00:00Z", BOUE, 4, 4, "AAAAAAAAAAA"))
    connection.execute(insert, ("2026-11-17T09:30:00Z", BOUE, 8, 20, "AAAAAAAAAAA"))  # replaces the first one
    connection.execute(insert, ("2026-11-17T09:00:00Z", BOUE, 2, 6, "BBBBBBBBBBB"))
    connection.execute(insert, ("2026-11-17T09:10:00Z", BOUE, 0, 0, "BBBBBBBBBBB"))  # B cleared it
    typed = load_manual(connection)[BOUE]
    assert (typed.units, typed.experience) == (18, 70)
    assert (own_manual(connection)[BOUE].units, own_manual(connection)[BOUE].experience) == (10, 50)
    store.close()


def test_totals_kept_in_config_json_by_older_versions_move_into_the_database_once(tmp_path) -> None:
    config = tmp_path / "config.json"
    save_config(config, {"server": "Brial", PET_MANUAL_KEY: {str(BOUE): {"units": 7, "experience": 21}, "x": {}}})
    store = open_store(tmp_path)
    assert import_config_manual(store.connection, config) == 1
    assert (load_manual(store.connection)[BOUE].units, load_manual(store.connection)[BOUE].experience) == (7, 21)
    assert PET_MANUAL_KEY not in load_config(config) and load_config(config)["server"] == "Brial"
    assert import_config_manual(store.connection, config) == 0
    store.close()


def test_search_finds_items_by_part_of_the_name(tmp_path) -> None:
    store = open_store(tmp_path)
    store.connection.executemany("INSERT INTO items (item_id, name_fr, type_fr) VALUES (?, ?, ?)",
                                 [(BOUE, "Boue du Boo", "Ressource"), (2, "Patte", "Ressource")])
    assert search_items(store.connection, "boue") == [(BOUE, "Boue du Boo")]
    assert search_items(store.connection, "  ") == []
    store.close()


def test_a_typed_resource_gets_a_row_without_any_observation(tmp_path) -> None:
    store = open_store(tmp_path)
    store.save_lot_price(LotPrice(BOUE, "Brial", 1, 100, "2026-11-12T09:00:00Z"))
    book = PriceBook.load(store.connection, "Brial")
    typed = {BOUE: add_and_load(store.connection)}
    rows = pet_rows(store.connection, "Brial", EVERYTHING, NAMES.get, lambda item: "Ressource", book, "last", typed)
    assert len(rows) == 1 and rows[0].manual and rows[0].per_unit == 5.0 and rows[0].kamas_per_xp == 20.0
    detail = pet_detail(store.connection, "Brial", BOUE, NAMES.get, lambda item: "Ressource", book, "last", typed)
    assert detail is not None and detail.upgrades == []
    store.close()


def add_and_load(connection):
    add_manual(connection, BOUE, 10, 50)
    return load_manual(connection)[BOUE]


@pytest.mark.parametrize("text, expected", [("12", 12), (" 1 500 ", 1500), ("0", None), ("-3", None), ("abc", None)])
def test_counts_are_strictly_positive_whole_numbers(text, expected) -> None:
    assert parse_count(text) == expected


def test_search_ignores_case_and_accents() -> None:
    import sqlite3
    from opendofusdata.item_search import search_items
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE items (item_id INTEGER, name_fr TEXT)")
    connection.execute("INSERT INTO items VALUES (1, 'Épée Ténébreuse')")
    assert search_items(connection, "epee tenebr") == [(1, "Épée Ténébreuse")]
    assert search_items(connection, "ÉPÉE") == [(1, "Épée Ténébreuse")]
