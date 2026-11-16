"""The reading store: batch insert with duplicates, change feed, latest page and the purges."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest

from keyserver.readings_store import RETENTION_DAYS, ReadingStore, open_readings
from keyserver.schemas import Reading

ALICE = "AAAAAAAAAAA"
BOB = "BBBBBBBBBBB"
NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def store() -> Iterator[ReadingStore]:
    readings = open_readings(":memory:")
    yield readings
    readings.close()


def reading(item_id: int = 1, price: int = 100, minutes_ago: int = 5, server: str = "Brial", lot_size: int = 1) -> Reading:
    moment = NOW - timedelta(minutes=minutes_ago)
    return Reading.model_construct(server=server, item_id=item_id, lot_size=lot_size, price=price, observed_at=moment)


def test_retention_is_seven_days() -> None:
    assert RETENTION_DAYS == 7


def test_add_batch_counts_accepted_and_duplicates(store: ReadingStore) -> None:
    assert store.add_batch(ALICE, [reading()]) == (1, 0)
    assert store.add_batch(ALICE, [reading()]) == (0, 1)
    assert len(store.changes_since(BOB, 0, 10)) == 1


def test_same_reading_from_two_keys_is_stored_twice(store: ReadingStore) -> None:
    store.add_batch(ALICE, [reading()])
    assert store.add_batch(BOB, [reading()]) == (1, 0)


def test_a_batch_mixes_new_and_known_readings(store: ReadingStore) -> None:
    store.add_batch(ALICE, [reading(item_id=1)])
    assert store.add_batch(ALICE, [reading(item_id=1), reading(item_id=2)]) == (1, 1)


def test_changes_since_excludes_own_readings_and_orders_by_seq(store: ReadingStore) -> None:
    store.add_batch(ALICE, [reading(item_id=1)])
    store.add_batch(BOB, [reading(item_id=2), reading(item_id=3)])
    changes = store.changes_since(ALICE, 0, 10)
    assert [stored.item_id for stored in changes] == [2, 3]
    assert changes[0].seq < changes[1].seq


def test_changes_since_respects_limit_and_since(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading(item_id=number) for number in range(1, 6)])
    first = store.changes_since(ALICE, 0, 2)
    assert [stored.item_id for stored in first] == [1, 2]
    assert [stored.item_id for stored in store.changes_since(ALICE, first[-1].seq, 10)] == [3, 4, 5]


def test_changes_carry_the_sender_key_id(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading()])
    assert store.changes_since(ALICE, 0, 10)[0].key_id == BOB


def test_dates_roundtrip_as_utc_iso_seconds(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading(minutes_ago=0)])
    stored = store.changes_since(ALICE, 0, 10)[0]
    assert stored.observed_at == "2026-11-16T12:00:00Z"
    assert (stored.server, stored.lot_size, stored.price) == ("Brial", 1, 100)


def test_latest_page_returns_latest_per_natural_key_of_other_keys(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading(price=100, minutes_ago=30), reading(price=120, minutes_ago=10)])
    store.add_batch(BOB, [reading(item_id=2, price=5)])
    page = store.latest_page(ALICE, 0, 10)
    assert sorted((stored.item_id, stored.price) for stored in page) == [(1, 120), (2, 5)]


def test_latest_page_ignores_own_readings(store: ReadingStore) -> None:
    store.add_batch(ALICE, [reading()])
    assert store.latest_page(ALICE, 0, 10) == []


def test_latest_page_pages_with_after(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading(item_id=number) for number in range(1, 5)])
    first = store.latest_page(ALICE, 0, 3)
    second = store.latest_page(ALICE, first[-1].seq, 3)
    assert [stored.item_id for stored in first + second] == [1, 2, 3, 4]


def test_purge_older_than_removes_only_old_readings(store: ReadingStore) -> None:
    store.add_batch(BOB, [reading(item_id=1, minutes_ago=60 * 24 * 8), reading(item_id=2, minutes_ago=60 * 24 * 6)])
    assert store.purge_older_than(NOW - timedelta(days=RETENTION_DAYS)) == 1
    assert [stored.item_id for stored in store.changes_since(ALICE, 0, 10)] == [2]


def test_purge_key_removes_only_that_key(store: ReadingStore) -> None:
    store.add_batch(ALICE, [reading(item_id=1)])
    store.add_batch(BOB, [reading(item_id=2)])
    assert store.purge_key(ALICE) == 1
    assert [stored.item_id for stored in store.changes_since("CCCCCCCCCCC", 0, 10)] == [2]
    assert store.purge_key(ALICE) == 0


def test_highest_seq_is_zero_when_empty_then_grows(store: ReadingStore) -> None:
    assert store.highest_seq() == 0
    store.add_batch(ALICE, [reading()])
    assert store.highest_seq() == 1
