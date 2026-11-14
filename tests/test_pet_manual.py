"""Experience typed by the player: storage, search, merge into the rows and the form."""

import pytest

from opendofusdata.item_search import search_items
from opendofusdata.pet_manual_form import parse_count
from opendofusdata.pet_manual_store import add_manual, load_manual, remove_manual
from opendofusdata.pets_view_data import pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.records import LotPrice
from tests.view_page_helpers import open_store

BOUE = 1001
NAMES = {BOUE: "Boue du Boo"}
EVERYTHING = (None, None)


def test_typed_experience_is_added_up_and_can_be_removed(tmp_path) -> None:
    path = tmp_path / "config.json"
    assert add_manual(path, BOUE, 10, 50) and add_manual(path, BOUE, 5, 25)
    typed = load_manual(path)[BOUE]
    assert (typed.units, typed.experience, typed.feedings) == (15, 75, 0)
    assert remove_manual(path, BOUE) and load_manual(path) == {}


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
    typed = {BOUE: add_and_load(tmp_path)}
    rows = pet_rows(store.connection, "Brial", EVERYTHING, NAMES.get, lambda item: "Ressource", book, "last", typed)
    assert len(rows) == 1 and rows[0].manual and rows[0].per_unit == 5.0 and rows[0].kamas_per_xp == 20.0
    detail = pet_detail(store.connection, "Brial", BOUE, NAMES.get, lambda item: "Ressource", book, "last", typed)
    assert detail is not None and detail.upgrades == []
    store.close()


def add_and_load(tmp_path):
    path = tmp_path / "config.json"
    add_manual(path, BOUE, 10, 50)
    return load_manual(path)[BOUE]


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
