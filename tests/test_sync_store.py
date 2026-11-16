"""Pending readings, sent marks, remote insertion and the sync state of the local database."""

import sqlite3
from datetime import datetime, timezone

import pytest

from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore
from opendofusdata.sync_store import (
    MIN_RESEND_SECONDS, PendingReading, get_state, insert_remote, mark_sent, pending_readings, set_state,
)

SENT_AT = "2026-11-16T12:00:00Z"


@pytest.fixture
def store() -> PriceStore:
    return PriceStore(":memory:")


def add(store: PriceStore, item_id: int = 1, price: int = 100, captured_at: str = "2026-11-16T10:00:00Z",
        lot_size: int = 1) -> None:
    store.save_lot_price(LotPrice(item_id, "Brial", lot_size, price, captured_at))


def send_all(store: PriceStore) -> list[PendingReading]:
    rows = pending_readings(store.connection, 100)
    mark_sent(store.connection, [row.row_id for row in rows], SENT_AT)
    return rows


def test_resend_delay_is_one_hour() -> None:
    assert MIN_RESEND_SECONDS == 3600


def test_pending_returns_unsent_local_rows_oldest_first_up_to_limit(store: PriceStore) -> None:
    add(store, 2, captured_at="2026-11-16T11:00:00Z")
    add(store, 1, captured_at="2026-11-16T10:00:00Z")
    add(store, 3, captured_at="2026-11-16T12:00:00Z")
    rows = pending_readings(store.connection, 2)
    assert [(row.item_id, row.captured_at) for row in rows] == [(1, "2026-11-16T10:00:00Z"),
                                                               (2, "2026-11-16T11:00:00Z")]
    assert rows[0] == PendingReading(rows[0].row_id, 1, "Brial", 1, 100, "2026-11-16T10:00:00Z")


def test_pending_ignores_remote_and_sent_rows(store: PriceStore) -> None:
    add(store, 1)
    send_all(store)
    insert_remote(store.connection, [remote(item_id=2)], SENT_AT)
    assert pending_readings(store.connection, 10) == []


def test_unchanged_price_within_an_hour_is_skipped_and_marked_sent(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T10:00:00Z")
    send_all(store)
    add(store, 1, 100, "2026-11-16T10:30:00Z")
    assert pending_readings(store.connection, 10) == []
    assert store.connection.execute("SELECT COUNT(*) FROM lot_prices WHERE synced_at IS NULL").fetchone() == (0,)
    stamp = store.connection.execute("SELECT synced_at FROM lot_prices WHERE captured_at LIKE '%10:30%'").fetchone()[0]
    assert stamp == "skipped"  # marked apart from really sent rows, so it is never a reference for the filter


def test_unchanged_price_after_an_hour_is_sent(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T10:00:00Z")
    send_all(store)
    add(store, 1, 100, "2026-11-16T11:00:01Z")
    assert [row.captured_at for row in pending_readings(store.connection, 10)] == ["2026-11-16T11:00:01Z"]


def test_changed_price_is_sent_at_once(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T10:00:00Z")
    send_all(store)
    add(store, 1, 101, "2026-11-16T10:01:00Z")
    assert [row.price for row in pending_readings(store.connection, 10)] == [101]


def test_another_lot_size_is_a_different_key(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T10:00:00Z", lot_size=1)
    send_all(store)
    add(store, 1, 100, "2026-11-16T10:10:00Z", lot_size=10)
    assert len(pending_readings(store.connection, 10)) == 1


def test_mark_sent_sets_synced_at(store: PriceStore) -> None:
    add(store, 1)
    rows = pending_readings(store.connection, 10)
    mark_sent(store.connection, [row.row_id for row in rows], SENT_AT)
    assert store.connection.execute("SELECT synced_at FROM lot_prices").fetchone() == (SENT_AT,)


def remote(item_id: int = 1, price: int = 120, key_id: str = "BBBBBBBBBBB",
           observed_at: str = "2026-11-16T09:00:00Z") -> dict[str, object]:
    return {"seq": 1, "key_id": key_id, "server": "Brial", "item_id": item_id, "lot_size": 1, "price": price,
            "observed_at": observed_at}


def test_insert_remote_adds_rows_with_remote_origin_synced_at_and_source_key_id(store: PriceStore) -> None:
    assert insert_remote(store.connection, [remote()], SENT_AT) == 1
    assert store.connection.execute(
        "SELECT item_id, server, lot_size, price, captured_at, origin, synced_at, source_key_id FROM lot_prices"
    ).fetchall() == [(1, "Brial", 1, 120, "2026-11-16T09:00:00Z", "remote", SENT_AT, "BBBBBBBBBBB")]


def test_insert_remote_ignores_known_rows_and_counts_new_ones(store: PriceStore) -> None:
    insert_remote(store.connection, [remote()], SENT_AT)
    assert insert_remote(store.connection, [remote(), remote(item_id=2)], SENT_AT) == 1


def test_state_roundtrip_and_default_none(store: PriceStore) -> None:
    assert get_state(store.connection, "cursor") is None
    set_state(store.connection, "cursor", "12")
    set_state(store.connection, "cursor", "15")
    assert get_state(store.connection, "cursor") == "15"


def test_remote_rows_appear_in_latest_prices_and_history(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T08:00:00Z")
    insert_remote(store.connection, [remote(item_id=1, price=130, observed_at="2026-11-16T09:00:00Z")], SENT_AT)
    assert [lot.price for lot in store.latest_prices(1)] == [130]
    assert [lot.price for lot in store.price_history(1, 1)] == [100, 130]


def test_the_connection_type_is_plain_sqlite(store: PriceStore) -> None:
    assert isinstance(store.connection, sqlite3.Connection)


NOW_FOR_AGE = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)


def pending_at(store: PriceStore, limit: int = 100) -> list[PendingReading]:
    return pending_readings(store.connection, limit, NOW_FOR_AGE)


def test_a_price_that_returns_to_an_earlier_value_is_sent(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T10:00:00Z")
    send_all_at(store)
    add(store, 1, 200, "2026-11-16T10:10:00Z")
    send_all_at(store)
    add(store, 1, 100, "2026-11-16T10:20:00Z")
    assert [row.price for row in pending_at(store)] == [100]


def test_skipped_rows_never_chain_into_a_permanent_silence(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-16T08:00:00Z")
    send_all_at(store)
    add(store, 1, 100, "2026-11-16T08:50:00Z")
    add(store, 1, 100, "2026-11-16T09:40:00Z")
    assert [row.captured_at for row in pending_at(store)] == ["2026-11-16T09:40:00Z"]


def send_all_at(store: PriceStore) -> None:
    rows = pending_at(store)
    mark_sent(store.connection, [row.row_id for row in rows], SENT_AT)


def test_rows_older_than_the_retention_are_never_sent(store: PriceStore) -> None:
    add(store, 1, 100, "2026-11-01T10:00:00Z")
    add(store, 2, 100, "2026-11-10T12:00:01Z")
    assert [row.item_id for row in pending_at(store)] == [2]
    assert store.connection.execute("SELECT COUNT(*) FROM lot_prices WHERE synced_at IS NULL").fetchone() == (1,)


def test_rows_the_server_would_refuse_are_skipped_not_retried_forever(store: PriceStore) -> None:
    add(store, 1, 10**12 + 1, "2026-11-16T10:00:00Z")
    add(store, 10_000_001, 5, "2026-11-16T10:01:00Z")
    store.save_lot_price(LotPrice(3, "=cmd|' /C calc'!A0", 1, 5, "2026-11-16T10:02:00Z"))
    store.save_lot_price(LotPrice(4, "Brial", 1, 5, "2026-11-16T10:03:00Z"))
    assert [row.item_id for row in pending_at(store)] == [4]
