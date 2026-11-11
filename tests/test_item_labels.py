"""Tests for the database item-name lookup."""

import sqlite3
from contextlib import closing

from opendofusdata.item_labels import (
    UNKNOWN_ITEM_NAME, UNKNOWN_ITEM_TYPE, item_labeler_for_database, load_item_labelers,
)


def test_labeler_without_items_table_gives_na() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        label, category = load_item_labelers(connection)
        assert (label(307), category(307)) == (UNKNOWN_ITEM_NAME, UNKNOWN_ITEM_TYPE)


def test_labeler_gives_names_and_na_for_gaps() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("CREATE TABLE items (item_id INTEGER PRIMARY KEY, name_fr TEXT, type_fr TEXT)")
        connection.execute("INSERT INTO items VALUES (307, 'Ailes de Moskito', 'Ressource')")
        label, category = load_item_labelers(connection)
    assert (label(307), category(307)) == ("Ailes de Moskito", "Ressource")
    assert (label(1), category(1)) == (UNKNOWN_ITEM_NAME, UNKNOWN_ITEM_TYPE)


def test_labeler_for_a_missing_database_gives_na(tmp_path) -> None:
    label = item_labeler_for_database(str(tmp_path / "absent.db"))
    assert label(307) == UNKNOWN_ITEM_NAME
    assert not (tmp_path / "absent.db").exists()  # looking never creates the file


def test_labeler_for_a_database_gives_names(tmp_path) -> None:
    path = tmp_path / "names.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE items (item_id INTEGER PRIMARY KEY, name_fr TEXT, type_fr TEXT)")
        connection.execute("INSERT INTO items VALUES (307, 'Ailes de Moskito', 'Ressource')")
        connection.commit()
    label = item_labeler_for_database(str(path))
    assert (label(307), label(1)) == ("Ailes de Moskito", UNKNOWN_ITEM_NAME)


def test_labeler_for_a_corrupt_database_gives_na(tmp_path) -> None:
    path = tmp_path / "broken.db"
    path.write_bytes(b"not a database at all" * 100)
    assert item_labeler_for_database(str(path))(307) == UNKNOWN_ITEM_NAME
