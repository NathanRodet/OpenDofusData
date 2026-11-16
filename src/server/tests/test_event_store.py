"""The journal of shared events (breakings, pet feedings): batches, duplicates, feeds and purges."""

from datetime import datetime, timedelta, timezone

import pytest

from keyserver.event_schemas import BrokenEvent
from keyserver.readings_store import ReadingStore, open_readings

ALICE, BOB = "AAAAAAAAAAA", "BBBBBBBBBBB"
NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
BROKEN = "broken"
PET = "pet"


@pytest.fixture
def store() -> ReadingStore:
    return open_readings(":memory:")


def broken(item_id: int = 1, minutes_ago: int = 5) -> BrokenEvent:
    return BrokenEvent.model_construct(server="Brial", item_id=item_id, quantity=2, coefficient=0.5,
                                       runes=[[10, 3], [11, 1]], observed_at=NOW - timedelta(minutes=minutes_ago))


def test_a_batch_is_stored_and_a_repeat_counts_as_duplicates(store: ReadingStore) -> None:
    assert store.events.add_batch(BROKEN, ALICE, [broken(1), broken(2)]) == (2, 0)
    assert store.events.add_batch(BROKEN, ALICE, [broken(1)]) == (0, 1)


def test_the_change_feed_returns_other_keys_events_of_that_kind_only(store: ReadingStore) -> None:
    store.events.add_batch(BROKEN, ALICE, [broken(1)])
    store.events.add_batch(BROKEN, BOB, [broken(2)])
    store.events.add_batch(PET, BOB, [broken(3)])
    page = store.events.changes_since(BROKEN, ALICE, 0, 10)
    assert [(event.key_id, event.payload["item_id"]) for event in page] == [(BOB, 2)]
    assert page[0].observed_at == "2026-11-16T11:55:00Z" and page[0].payload["runes"] == [[10, 3], [11, 1]]


def test_the_own_feed_returns_the_callers_events_only_and_pages(store: ReadingStore) -> None:
    store.events.add_batch(BROKEN, ALICE, [broken(number) for number in range(1, 5)])
    store.events.add_batch(BROKEN, BOB, [broken(9)])
    first = store.events.own_page(BROKEN, ALICE, 0, 3)
    second = store.events.own_page(BROKEN, ALICE, first[-1].seq, 3)
    assert [event.payload["item_id"] for event in first + second] == [1, 2, 3, 4]


def test_old_events_are_purged_with_the_readings(store: ReadingStore) -> None:
    store.events.add_batch(BROKEN, ALICE, [broken(1, minutes_ago=60 * 24 * 15), broken(2, minutes_ago=5)])
    assert store.events.purge_older_than(NOW - timedelta(days=14)) == 1
    assert [event.payload["item_id"] for event in store.events.own_page(BROKEN, ALICE, 0, 10)] == [2]


def test_purging_a_key_removes_its_events_everywhere(store: ReadingStore) -> None:
    store.events.add_batch(BROKEN, ALICE, [broken(1)])
    store.events.add_batch(PET, ALICE, [broken(2)])
    store.events.add_batch(BROKEN, BOB, [broken(3)])
    assert store.purge_key(ALICE) == 2
    assert [event.key_id for event in store.events.changes_since(BROKEN, "CCCCCCCCCCC", 0, 10)] == [BOB]
