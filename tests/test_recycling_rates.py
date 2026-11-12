"""The expected recycling yield (DofusDB's recyclingNuggets x quantity x the personal factor)."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest

from opendofusdata.item_labels import rates_for_database
from opendofusdata.item_names import ItemEntry, ItemNames
from opendofusdata.log_feed import entry_from_record, format_log_row
from opendofusdata.names_build import build_entries, write_items_csv
from opendofusdata.names_db import replace_items
from opendofusdata.recycling import PERSONAL_FACTOR, expected_nuggets
from opendofusdata.records import RecyclingEvent
from opendofusdata.storage import PriceStore

MOMENT = datetime(2026, 11, 12, 0, 24, 28, tzinfo=timezone.utc)
RATES = {310: 0.005495169082125605, 417: 0.011594339622641508, 2278: 0.06823607173890404, 15073: 0.24435}
NAMES = {310: "Os de Chafer", 417: "Boue du Boo", 13714: "Dent de Larve Rubis"}


def rate_of(item_id: int) -> float | None:
    return RATES.get(item_id)


@pytest.mark.parametrize("items, shown", [
    (((310, 100),), 0.33), (((417, 10),), 0.07), (((2278, 10),), 0.41), (((15073, 10),), 1.47),
    (((310, 1000),), 3.30), (((310, 190),), 0.63), (((310, 10),), 0.03), (((310, 1),), 0.0),
])
def test_the_expected_yield_matches_what_the_game_displayed(items, shown) -> None:
    assert round(expected_nuggets(items, rate_of), 2) == shown


def test_the_four_items_window_sums_the_unrounded_yields() -> None:
    window = ((310, 100), (15073, 10), (417, 10), (2278, 10))
    assert expected_nuggets(window, rate_of) == pytest.approx(2.2748, abs=0.001)


def test_an_item_without_a_known_rate_makes_the_yield_unknown() -> None:
    assert expected_nuggets(((310, 100), (999, 1)), rate_of) is None
    assert expected_nuggets((), rate_of) is None


def test_a_known_zero_rate_counts_as_zero() -> None:
    assert expected_nuggets(((5, 10),), {5: 0.0}.get) == 0.0


def test_the_personal_factor_is_the_one_found_in_game() -> None:
    assert PERSONAL_FACTOR == 0.6


def raw(**overrides) -> dict:
    return {"id": 1, "name": {"fr": "Objet"}, "level": 1, "typeId": 1, **overrides}


def test_the_download_keeps_a_valid_recycling_rate_and_drops_anything_else() -> None:
    entries = build_entries([raw(recyclingNuggets=0.5), raw(id=2, recyclingNuggets=0), raw(id=3),
                             raw(id=4, recyclingNuggets="x"), raw(id=5, recyclingNuggets=-1),
                             raw(id=6, recyclingNuggets=True), raw(id=7, recyclingNuggets=float("nan")),
                             raw(id=8, recyclingNuggets=float("inf"))], {1: "T"}).entries
    assert [entry.recycling_nuggets for entry in entries] == [0.5, 0.0, None, None, None, None, None, None]


def test_the_rate_survives_the_csv_round_trip(tmp_path: Path) -> None:
    write_items_csv([ItemEntry(310, "Os de Chafer", 5, "Os", RATES[310]), ItemEntry(1, "Sans taux", 1, "T", None)],
                    tmp_path / "items.csv")
    loaded = {entry.item_id: entry for entry in ItemNames.load(tmp_path / "items.csv").entries()}
    assert loaded[310].recycling_nuggets == RATES[310]
    assert loaded[1].recycling_nuggets is None


def test_an_older_four_column_csv_still_loads_without_rates(tmp_path: Path) -> None:
    path = tmp_path / "old.csv"
    path.write_text("id,name_fr,level,type_fr\n310,Os de Chafer,5,Os\n", encoding="utf-8")
    assert [entry.recycling_nuggets for entry in ItemNames.load(path).entries()] == [None]


def test_the_database_keeps_the_rates_and_the_lookup_reads_them(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "r.db"))
    try:
        replace_items(store.connection, [ItemEntry(310, "Os de Chafer", 5, "Os", RATES[310]),
                                         ItemEntry(1, "Sans taux", 1, "T", None)])
    finally:
        store.close()
    lookup = rates_for_database(str(tmp_path / "r.db"))
    assert lookup(310) == RATES[310]
    assert lookup(1) is None
    assert lookup(999) is None


def test_the_lookup_without_a_database_knows_no_rate(tmp_path) -> None:
    assert rates_for_database(str(tmp_path / "absent.db"))(310) is None


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


def test_the_yields_view_compares_each_recycling_with_its_expected_value(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "v.db"))
    try:
        replace_items(store.connection, [ItemEntry(310, "Os de Chafer", 5, "Os", RATES[310])])
        store.save_record(RecyclingEvent("Brial", ((310, 1000),), 3, "2026-11-11T19:18:30Z"))
        store.save_record(RecyclingEvent("Brial", ((310, 1), (999, 5)), 0, "2026-11-11T19:18:03Z"))
        rows = store.connection.execute("SELECT obtained, expected FROM recycling_yields ORDER BY captured_at").fetchall()
    finally:
        store.close()
    assert rows[0] == (0, pytest.approx(0.0033, abs=1e-4))  # the unknown item counts as 0
    assert rows[1] == (3, pytest.approx(3.2971, abs=1e-3))


def test_the_log_line_shows_the_expected_yield_next_to_the_result() -> None:
    event = RecyclingEvent("Brial", ((13714, 4),), 0, "t")
    entry = entry_from_record(event, MOMENT)
    rates = {13714: 0.02916}.get
    row = format_log_row(entry, NAMES.__getitem__, rates)
    assert row[1:] == ("Recyclage", "Dent de Larve Rubis ×4", "att. 0,07", "0 Pépite")


def test_the_log_line_keeps_the_object_count_when_a_rate_is_unknown_or_not_given() -> None:
    entry = entry_from_record(RecyclingEvent("Brial", ((13714, 4),), 0, "t"), MOMENT)
    assert format_log_row(entry, NAMES.__getitem__, {}.get)[3] == "1 objet"
    assert format_log_row(entry, NAMES.__getitem__)[3] == "1 objet"
