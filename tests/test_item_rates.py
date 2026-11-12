"""The recycling rate column kept with the item names (DofusDB recyclingNuggets), for the CSV and the database."""

import sqlite3
from contextlib import closing
from pathlib import Path

from opendofusdata.item_names import ItemEntry, ItemNames
from opendofusdata.names_build import build_entries, write_items_csv
from opendofusdata.names_db import replace_items
from opendofusdata.storage import PriceStore

OS_DE_CHAFER_RATE = 0.005495169082125605


def raw(**overrides) -> dict:
    return {"id": 1, "name": {"fr": "Objet"}, "level": 1, "typeId": 1, **overrides}


def test_the_download_keeps_a_valid_recycling_rate_and_drops_anything_else() -> None:
    entries = build_entries([raw(recyclingNuggets=0.5), raw(id=2, recyclingNuggets=0), raw(id=3),
                             raw(id=4, recyclingNuggets="x"), raw(id=5, recyclingNuggets=-1),
                             raw(id=6, recyclingNuggets=True), raw(id=7, recyclingNuggets=float("nan")),
                             raw(id=8, recyclingNuggets=float("inf"))], {1: "T"}).entries
    assert [entry.recycling_nuggets for entry in entries] == [0.5, 0.0, None, None, None, None, None, None]


def test_the_rate_survives_the_csv_round_trip(tmp_path: Path) -> None:
    write_items_csv([ItemEntry(310, "Os de Chafer", 5, "Os", OS_DE_CHAFER_RATE), ItemEntry(1, "Sans taux", 1, "T", None)],
                    tmp_path / "items.csv")
    loaded = {entry.item_id: entry for entry in ItemNames.load(tmp_path / "items.csv").entries()}
    assert loaded[310].recycling_nuggets == OS_DE_CHAFER_RATE
    assert loaded[1].recycling_nuggets is None


def test_an_older_four_column_csv_still_loads_without_rates(tmp_path: Path) -> None:
    path = tmp_path / "old.csv"
    path.write_text("id,name_fr,level,type_fr\n310,Os de Chafer,5,Os\n", encoding="utf-8")
    assert [entry.recycling_nuggets for entry in ItemNames.load(path).entries()] == [None]


def test_the_database_keeps_the_rates(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "r.db"))
    try:
        replace_items(store.connection, [ItemEntry(310, "Os de Chafer", 5, "Os", OS_DE_CHAFER_RATE),
                                         ItemEntry(1, "Sans taux", 1, "T", None)])
    finally:
        store.close()
    with closing(sqlite3.connect(tmp_path / "r.db")) as connection:
        rows = connection.execute("SELECT item_id, recycling_nuggets FROM items ORDER BY item_id").fetchall()
    assert rows == [(1, None), (310, OS_DE_CHAFER_RATE)]


def test_an_older_database_gets_the_rate_column_and_keeps_its_names(tmp_path) -> None:
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        connection.execute("CREATE TABLE items (item_id INTEGER PRIMARY KEY, name_fr TEXT NOT NULL, level INTEGER, "
                           "type_fr TEXT NOT NULL DEFAULT '')")
        connection.execute("INSERT INTO items VALUES (310, 'Os de Chafer', 5, 'Os')")
        connection.commit()
    PriceStore(str(tmp_path / "old.db")).close()
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        assert connection.execute("SELECT name_fr, recycling_nuggets FROM items").fetchall() == [("Os de Chafer", None)]
    PriceStore(str(tmp_path / "old.db")).close()  # opening again changes nothing


def test_an_old_database_loses_the_recycling_table_and_view(tmp_path) -> None:
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        connection.execute("CREATE TABLE recycling_events (id INTEGER PRIMARY KEY, nuggets INTEGER)")
        connection.execute("CREATE VIEW recycling_yields AS SELECT id FROM recycling_events")
        connection.commit()
    PriceStore(str(tmp_path / "old.db")).close()
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert not {"recycling_events", "recycling_yields"} & names
