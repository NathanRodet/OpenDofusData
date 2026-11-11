"""Tests for the database item-name lookup."""

import sqlite3
from contextlib import closing

from opendofusdata.item_labels import UNKNOWN_ITEM_NAME, load_item_labeler


def test_labeler_without_items_table_gives_na() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        assert load_item_labeler(connection)(307) == UNKNOWN_ITEM_NAME


def test_labeler_gives_names_and_na_for_gaps() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE items (item_id INTEGER PRIMARY KEY, name_fr TEXT)")
        connection.execute("INSERT INTO items VALUES (307, 'Ailes de Moskito')")
        label = load_item_labeler(connection)
    assert (label(307), label(1)) == ("Ailes de Moskito", UNKNOWN_ITEM_NAME)
