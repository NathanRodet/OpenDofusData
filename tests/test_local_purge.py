"""The optional local purge: rows older than fourteen days go, the latest price of each key and all user data stay."""

from datetime import datetime, timezone

import pytest

from opendofusdata.records import BrokenItem, LotPrice, MarketStats, PetFeeding, PetState
from opendofusdata.storage import PriceStore
from opendofusdata.sync_store import insert_remote, set_state
from opendofusdata.local_purge import LOCAL_RETENTION_DAYS, PurgeResult, purge_old_readings

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
OLD = "2026-11-01T10:00:00Z"
OLDER = "2026-10-20T10:00:00Z"
RECENT = "2026-11-15T10:00:00Z"
JUST_OVER = "2026-11-02T11:59:59Z"
JUST_UNDER = "2026-11-02T12:00:01Z"


@pytest.fixture
def store() -> PriceStore:
    return PriceStore(":memory:")


def lot(store: PriceStore, item_id: int, captured_at: str, price: int = 100, lot_size: int = 1) -> None:
    store.save_lot_price(LotPrice(item_id, "Brial", lot_size, price, captured_at))


def stats(store: PriceStore, item_id: int, captured_at: str, period: str = "24h", server: str = "Brial") -> None:
    store.save_market_stats(MarketStats(item_id, server, period, [(1, 2, 3)], 5, 6, 7, captured_at, captured_at,
                                        captured_at))


def remaining(store: PriceStore, table: str = "lot_prices", column: str = "captured_at") -> list[str]:
    return [row[0] for row in store.connection.execute(f"SELECT {column} FROM {table} ORDER BY {column}")]


def test_retention_is_fourteen_days() -> None:
    assert LOCAL_RETENTION_DAYS == 14


def test_old_rows_are_deleted_but_the_latest_of_each_key_is_kept(store: PriceStore) -> None:
    lot(store, 1, OLDER, 90)
    lot(store, 1, OLD, 100)
    lot(store, 2, OLDER, 50)
    result = purge_old_readings(store.connection, NOW)
    assert remaining(store) == [OLDER, OLD]  # item 2 keeps its only (latest) row, item 1 keeps OLD
    assert result == PurgeResult(lot_prices=1, market_stats=0)


def test_rows_within_fourteen_days_are_kept(store: PriceStore) -> None:
    lot(store, 1, OLD, 90)
    lot(store, 1, RECENT, 100)
    lot(store, 1, "2026-11-12T10:00:00Z", 95)
    purge_old_readings(store.connection, NOW)
    assert remaining(store) == ["2026-11-12T10:00:00Z", RECENT]


def test_the_boundary_is_exactly_fourteen_days(store: PriceStore) -> None:
    lot(store, 1, JUST_OVER, 1)
    lot(store, 1, JUST_UNDER, 2)
    lot(store, 1, RECENT, 3)
    lot(store, 2, JUST_OVER, 4)
    lot(store, 2, RECENT, 5)
    purge_old_readings(store.connection, NOW)
    assert remaining(store) == [JUST_UNDER, RECENT, RECENT]


def test_keys_are_item_server_and_lot_size(store: PriceStore) -> None:
    lot(store, 1, OLDER, 1, lot_size=1)
    lot(store, 1, OLD, 2, lot_size=10)
    store.save_lot_price(LotPrice(1, "Dakal", 1, 3, OLDER))
    purge_old_readings(store.connection, NOW)
    assert len(remaining(store)) == 3  # three different keys: each keeps its latest row


def test_remote_and_local_rows_are_treated_alike(store: PriceStore) -> None:
    lot(store, 1, OLDER)
    insert_remote(store.connection, [{"key_id": "BBBBBBBBBBB", "server": "Brial", "item_id": 1, "lot_size": 1,
                                      "price": 7, "observed_at": OLD}], "2026-11-16T11:00:00Z")
    result = purge_old_readings(store.connection, NOW)
    assert result.lot_prices == 1
    assert store.connection.execute("SELECT origin, price FROM lot_prices").fetchall() == [("remote", 7)]


def test_market_stats_follow_the_same_rule_per_item_server_period(store: PriceStore) -> None:
    stats(store, 1, OLDER)
    stats(store, 1, OLD)
    stats(store, 1, OLDER, period="7d")
    stats(store, 1, OLDER, server="Dakal")
    stats(store, 2, RECENT)
    result = purge_old_readings(store.connection, NOW)
    assert result == PurgeResult(lot_prices=0, market_stats=1)
    assert len(remaining(store, "market_stats")) == 4


def test_other_tables_are_untouched(store: PriceStore) -> None:
    lot(store, 1, OLDER)
    lot(store, 1, OLD)
    store.save_record(BrokenItem("Brial", 5, 1, 0.5, ((1, 2),), OLDER))
    state = PetState(1, 2, 3, 4)
    store.save_record(PetFeeding("Brial", 9, ((5, 100),), state, state, OLDER))
    store.connection.execute("INSERT INTO items (item_id, name_fr) VALUES (1, 'Ailes')")
    store.connection.execute("INSERT INTO servers (server_id, name_fr) VALUES (1, 'Brial')")
    set_state(store.connection, "cursor", "12")
    tables = ("broken_items", "pet_feedings", "items", "servers", "sync_state")
    before = {table: store.connection.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
    purge_old_readings(store.connection, NOW)
    after = {table: store.connection.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
    assert after == before and all(before.values())


def test_purge_twice_deletes_nothing_more(store: PriceStore) -> None:
    lot(store, 1, OLDER)
    lot(store, 1, OLD)
    purge_old_readings(store.connection, NOW)
    assert purge_old_readings(store.connection, NOW) == PurgeResult(0, 0)


def test_an_empty_database_is_fine(store: PriceStore) -> None:
    assert purge_old_readings(store.connection, NOW) == PurgeResult(0, 0)


def test_purge_database_file_works_on_a_real_file_and_startup_purge_obeys_the_setting(tmp_path) -> None:
    from opendofusdata.local_purge import purge_database_file, startup_purge
    from opendofusdata.purge_options import PURGE_KEY

    path = tmp_path / "prices.db"
    prices = PriceStore(str(path))
    lot(prices, 1, OLDER)
    lot(prices, 1, OLD)
    prices.close()
    assert startup_purge({}, str(path)) is None
    assert startup_purge({PURGE_KEY: False}, str(path)) is None
    assert startup_purge({PURGE_KEY: True}, str(path), clock=lambda: NOW) == PurgeResult(1, 0)
    assert purge_database_file(str(path), clock=lambda: NOW) == PurgeResult(0, 0)


def test_startup_purge_never_creates_a_missing_database(tmp_path) -> None:
    from opendofusdata.local_purge import startup_purge
    from opendofusdata.purge_options import PURGE_KEY

    missing = tmp_path / "absent.db"
    assert startup_purge({PURGE_KEY: True}, str(missing)) is None
    assert not missing.exists()


def test_startup_purge_survives_a_database_without_tables(tmp_path, caplog) -> None:
    import sqlite3

    from opendofusdata.local_purge import startup_purge
    from opendofusdata.purge_options import PURGE_KEY

    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    assert startup_purge({PURGE_KEY: True}, str(path)) is None
    assert any("purge" in record.getMessage().lower() for record in caplog.records)
