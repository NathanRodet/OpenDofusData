"""Tests of the Familiers view data."""

from datetime import datetime, timezone

import pytest

from opendofusdata.pet_economy import PET_TOTAL_EXPERIENCE
from opendofusdata.pets_view_data import pet_detail, pet_rows
from opendofusdata.price_book import PriceBook
from opendofusdata.records import LotPrice, PetFeeding, PetState
from opendofusdata.storage import PriceStore

BOUE, PATTE, EYE, NOMOON = 1001, 1002, 1003, 9000
NAMES = {BOUE: "Boue du Boo", PATTE: "Patte de Gruche", EYE: "Œil", NOMOON: "Nomoon"}


def name_of(item_id: int) -> str:
    return NAMES.get(item_id, "N/A")


def type_of(item_id: int) -> str:
    return "Ressource"


def feeding(resources, before: int, after: int, stamp: str = "10:00") -> PetFeeding:
    return PetFeeding("Brial", NOMOON, tuple(resources), PetState(35, before, 1000, 0),
                      PetState(35, after, 1000, 0), f"2026-11-12T{stamp}:00Z")


@pytest.fixture
def store(tmp_path):
    store = PriceStore(str(tmp_path / "p.db"))
    store.save_lot_price(LotPrice(PATTE, "Brial", 1, 240, "2026-11-12T09:00:00Z"))
    yield store
    store.close()


def rows_of(store: PriceStore, window=(None, None)):
    book = PriceBook.load(store.connection, "Brial")
    return pet_rows(store.connection, "Brial", window, name_of, type_of, book, "last"), book


def test_rows_are_ordered_by_kamas_per_xp_with_unpriced_last(store) -> None:
    store.save_record(feeding([(BOUE, 9)], 100, 101))
    store.save_record(feeding([(PATTE, 1)], 101, 103, "10:05"))
    rows, _ = rows_of(store)
    assert [row.name for row in rows] == ["Patte de Gruche", "Boue du Boo"]
    patte, boue = rows
    assert (patte.per_unit, patte.kamas_per_xp, patte.cost) == (2.0, 120.0, 120 * PET_TOTAL_EXPERIENCE)
    assert (boue.per_unit, boue.kamas_per_xp, boue.cost) == (1 / 9, None, None)
    assert patte.last_seen == datetime(2026, 11, 12, 10, 5, tzinfo=timezone.utc)


def test_a_mixed_upgrade_is_only_in_the_detail(store) -> None:
    store.save_record(feeding([(PATTE, 1), (EYE, 2)], 0, 5))
    rows, book = rows_of(store)
    assert rows == []
    detail = pet_detail(store.connection, "Brial", EYE, name_of, type_of, book, "last")
    (upgrade,) = detail.upgrades
    assert (upgrade.mixed, upgrade.gain, upgrade.units, upgrade.pet_name) == (True, None, 2, "Nomoon")
    assert detail.row.feedings == 0 and detail.row.per_unit is None


def test_the_detail_lists_the_upgrades_newest_first(store) -> None:
    store.save_record(feeding([(PATTE, 1)], 101, 103, "10:05"))
    store.save_record(feeding([(PATTE, 2)], 103, 106, "08:00"))
    _, book = rows_of(store)
    detail = pet_detail(store.connection, "Brial", PATTE, name_of, type_of, book, "last")
    assert [upgrade.gain for upgrade in detail.upgrades] == [2, 3]


def test_the_server_is_respected_and_an_unused_resource_has_no_detail(store) -> None:
    other = PetFeeding("Kourial", NOMOON, ((PATTE, 1),), PetState(35, 0, 9, 0), PetState(35, 2, 9, 0), "2026-11-12T10:00:00Z")
    store.save_record(other)
    rows, book = rows_of(store)
    assert rows == []
    assert pet_detail(store.connection, "Brial", PATTE, name_of, type_of, book, "last") is None


def test_empty_database(store) -> None:
    assert rows_of(store)[0] == []


def test_bulk_price_is_the_cheapest_unit_price_of_the_x100_and_x1000_lots() -> None:
    from opendofusdata.price_rules import ItemPrices, bulk_unit_price

    assert bulk_unit_price(ItemPrices({1: 900, 100: 80_000, 1000: 700_000}, None, None)) == 700.0
    assert bulk_unit_price(ItemPrices({1: 900, 10: 8_000}, None, None)) is None
    assert bulk_unit_price(None) is None


def test_pet_price_is_the_recent_bulk_price_else_the_last_sale_else_an_old_bulk_price() -> None:
    from opendofusdata.price_rules import ItemPrices, pet_unit_price

    since = "2026-11-13T09:00:00Z"
    old = ItemPrices({100: 80_000}, None, None, None, {100: "2026-11-10T09:00:00Z"})
    assert pet_unit_price(old, 950.0, 1.0, since) == 950.0
    assert pet_unit_price(old, None, 1.0, since) == 800.0
    fresh = ItemPrices({100: 80_000}, None, None, None, {100: "2026-11-14T09:00:00Z"})
    assert pet_unit_price(fresh, 950.0, 1.0, since) == 800.0
    assert pet_unit_price(None, None, 7.0) == 7.0
