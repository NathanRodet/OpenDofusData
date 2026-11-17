"""The local side of the shared events: pending rows, sent marks, events received and restored."""

from datetime import datetime, timezone

import pytest

from opendofusdata.event_kinds import BROKEN, MANUAL, PET
from opendofusdata.event_sync_store import insert_other_events, insert_own_events, mark_events_sent, pending_events
from opendofusdata.records import BrokenItem, PetFeeding, PetState
from opendofusdata.storage import PriceStore
from opendofusdata.sync_store import SKIPPED

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
MOMENT = "2026-11-16T12:00:00Z"
STATE = PetState(5, 100, 200, 10)
AFTER = PetState(5, 150, 200, 10)


@pytest.fixture
def store() -> PriceStore:
    return PriceStore(":memory:")


def add_broken(store: PriceStore, item_id: int = 1, captured_at: str = "2026-11-16T10:00:00Z") -> None:
    store.save_record(BrokenItem("Brial", item_id, 2, 0.5, ((10, 3), (11, 1)), captured_at))


def add_pet(store: PriceStore, captured_at: str = "2026-11-16T10:00:00Z") -> None:
    store.save_record(PetFeeding("Brial", 7, ((20, 4),), STATE, AFTER, captured_at))


def remote_broken(item_id: int = 1, key_id: str = "BBBBBBBBBBB") -> dict[str, object]:
    return {"seq": 3, "key_id": key_id, "server": "Brial", "item_id": item_id, "quantity": 2, "coefficient": 0.5,
            "runes": [[10, 3], [11, 1]], "observed_at": "2026-11-15T09:00:00Z"}


def test_pending_rows_become_events_with_their_date_and_runes(store: PriceStore) -> None:
    add_broken(store)
    rows = pending_events(store.connection, BROKEN, 10, NOW)
    assert [row.event for row in rows] == [{
        "server": "Brial", "item_id": 1, "quantity": 2, "coefficient": 0.5, "runes": [[10, 3], [11, 1]],
        "observed_at": "2026-11-16T10:00:00Z"}]


def test_a_pet_feeding_becomes_an_event_with_both_states(store: PriceStore) -> None:
    add_pet(store)
    event = pending_events(store.connection, PET, 10, NOW)[0].event
    assert event["resources"] == [[20, 4]] and event["before"]["experience"] == 100
    assert event["after"]["experience"] == 150 and event["pet_item_id"] == 7


def test_sent_rows_are_not_pending_again(store: PriceStore) -> None:
    add_broken(store)
    rows = pending_events(store.connection, BROKEN, 10, NOW)
    mark_events_sent(store.connection, BROKEN, [row.row_id for row in rows], MOMENT)
    assert pending_events(store.connection, BROKEN, 10, NOW) == []


def test_rows_older_than_fourteen_days_or_refused_by_the_server_are_skipped(store: PriceStore) -> None:
    add_broken(store, 1, "2026-11-01T10:00:00Z")
    store.save_record(BrokenItem("Brial", 2, 0, 0.5, ((10, 3),), "2026-11-16T10:00:00Z"))
    add_broken(store, 3)
    assert [row.event["item_id"] for row in pending_events(store.connection, BROKEN, 10, NOW)] == [3]
    skipped = store.connection.execute("SELECT COUNT(*) FROM broken_items WHERE synced_at = ?", (SKIPPED,)).fetchone()
    assert skipped == (2,)


def test_other_players_events_are_stored_as_remote_rows_once(store: PriceStore) -> None:
    assert insert_other_events(store.connection, BROKEN, [remote_broken(), remote_broken()], MOMENT) == 1
    assert insert_other_events(store.connection, BROKEN, [remote_broken()], MOMENT) == 0
    row = store.connection.execute("SELECT origin, synced_at, source_key_id FROM broken_items").fetchone()
    assert row == ("remote", MOMENT, "BBBBBBBBBBB")


def test_two_players_may_report_the_same_breaking(store: PriceStore) -> None:
    insert_other_events(store.connection, BROKEN, [remote_broken(key_id="BBBBBBBBBBB")], MOMENT)
    assert insert_other_events(store.connection, BROKEN, [remote_broken(key_id="CCCCCCCCCCC")], MOMENT) == 1


def test_own_events_come_back_as_sent_local_rows_without_duplicates(store: PriceStore) -> None:
    add_broken(store, 1, "2026-11-15T09:00:00Z")
    assert insert_own_events(store.connection, BROKEN, [remote_broken(1), remote_broken(2)], MOMENT) == 1
    rows = store.connection.execute("SELECT item_id, origin, synced_at FROM broken_items ORDER BY item_id").fetchall()
    assert rows == [(1, "local", None), (2, "local", MOMENT)]


def test_a_pet_feeding_survives_the_round_trip(store: PriceStore) -> None:
    add_pet(store)
    event = pending_events(store.connection, PET, 10, NOW)[0].event
    other = PriceStore(":memory:")
    insert_other_events(other.connection, PET, [{**event, "seq": 1, "key_id": "BBBBBBBBBBB"}], MOMENT)
    original = PetFeeding("Brial", 7, ((20, 4),), STATE, AFTER, "2026-11-16T10:00:00Z")
    from opendofusdata.pets_store import pet_feedings

    assert pet_feedings(other.connection) == [original]


def test_typed_experience_is_sent_then_comes_back_for_the_other_players_and_for_me(store: PriceStore) -> None:
    from opendofusdata.pet_manual_store import add_manual, load_manual, own_manual

    add_manual(store.connection, 5, 10, 50, NOW)
    rows = pending_events(store.connection, MANUAL, 10, NOW)
    assert [row.event for row in rows] == [{"item_id": 5, "units": 10, "experience": 50, "observed_at": MOMENT}]
    mark_events_sent(store.connection, MANUAL, [row.row_id for row in rows], MOMENT)
    assert pending_events(store.connection, MANUAL, 10, NOW) == []
    other = {"seq": 4, "key_id": "BBBBBBBBBBB", "item_id": 5, "units": 2, "experience": 7,
             "observed_at": "2026-11-16T11:00:00Z"}
    assert insert_other_events(store.connection, MANUAL, [other], MOMENT) == 1
    assert (load_manual(store.connection)[5].units, load_manual(store.connection)[5].experience) == (12, 57)
    assert (own_manual(store.connection)[5].units, own_manual(store.connection)[5].experience) == (10, 50)
