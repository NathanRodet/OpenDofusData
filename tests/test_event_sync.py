"""The synchronisation of the shared events: send, receive, restore once, and keep going after a failure."""

from datetime import datetime, timezone

import pytest

from opendofusdata import event_sync
from opendofusdata.event_kinds import BROKEN, PET
from opendofusdata.records import BrokenItem, PetFeeding, PetState
from opendofusdata.storage import PriceStore
from opendofusdata.sync_api import SyncFailure
from opendofusdata.sync_engine import Progress, SyncOptions
from opendofusdata.sync_store import get_state

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
BASE = "https://sync.exemple.fr"
KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
BOTH = SyncOptions(BASE, KEY, True, True)
STATE = PetState(5, 100, 200, 10)


def event(item_id: int, seq: int, key_id: str = "BBBBBBBBBBB") -> dict[str, object]:
    return {"seq": seq, "key_id": key_id, "server": "Brial", "item_id": item_id, "quantity": 2, "coefficient": 0.5,
            "runes": [[10, 3]], "observed_at": "2026-11-15T09:00:00Z"}


class FakeEvents:
    """A double of the three event calls: records what was sent, serves canned pages per path."""

    def __init__(self) -> None:
        self.pushed: list[tuple[str, list]] = []
        self.changes: dict[str, list[tuple[list, int]]] = {}
        self.own: dict[str, list[tuple[list, int]]] = {}
        self.calls: list[str] = []
        self.failure: SyncFailure | None = None

    def push(self, base_url, key, kind, events):
        path = kind.path
        self.calls.append(f"push:{path}")
        if self.failure:
            raise self.failure
        self.pushed.append((path, list(events)))
        return len(events)

    def pull_changes(self, base_url, key, kind, since):
        path = kind.path
        self.calls.append(f"changes:{path}:{since}")
        pages = self.changes.get(path, [])
        return pages.pop(0) if pages else ([], since)

    def pull_own(self, base_url, key, kind, after):
        path = kind.path
        self.calls.append(f"own:{path}:{after}")
        pages = self.own.get(path, [])
        return pages.pop(0) if pages else ([], after)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> FakeEvents:
    fake = FakeEvents()
    monkeypatch.setattr(event_sync, "push_events", fake.push)
    monkeypatch.setattr(event_sync, "pull_event_changes", fake.pull_changes)
    monkeypatch.setattr(event_sync, "pull_event_own", fake.pull_own)
    return fake


@pytest.fixture
def store() -> PriceStore:
    return PriceStore(":memory:")


def run(store: PriceStore, options: SyncOptions = BOTH) -> Progress:
    progress = Progress()
    event_sync.sync_events(store.connection, options, lambda: NOW, progress)
    return progress


def test_local_breakings_and_pet_upgrades_are_sent_to_their_own_routes(store: PriceStore, server: FakeEvents) -> None:
    store.save_record(BrokenItem("Brial", 1, 2, 0.5, ((10, 3),), "2026-11-16T10:00:00Z"))
    store.save_record(PetFeeding("Brial", 7, ((20, 4),), STATE, STATE, "2026-11-16T10:00:00Z"))
    progress = run(store, SyncOptions(BASE, KEY, True, False))
    assert [path for path, _ in server.pushed] == ["/brisages", "/familiers"] and progress.sent == 2
    run(store, SyncOptions(BASE, KEY, True, False))
    assert len(server.pushed) == 2  # nothing is sent twice


def test_nothing_is_sent_when_sending_is_off(store: PriceStore, server: FakeEvents) -> None:
    store.save_record(BrokenItem("Brial", 1, 2, 0.5, ((10, 3),), "2026-11-16T10:00:00Z"))
    run(store, SyncOptions(BASE, KEY, False, True))
    assert server.pushed == []


def test_other_players_events_are_received_page_by_page_with_a_saved_cursor(store: PriceStore,
                                                                            server: FakeEvents) -> None:
    server.changes["/brisages"] = [([event(1, 4)], 4), ([event(2, 9)], 9)]
    progress = run(store, SyncOptions(BASE, KEY, False, True))
    assert progress.received == 2
    assert get_state(store.connection, "events_broken_cursor") == "9"
    assert "changes:/brisages:0" in server.calls and "changes:/brisages:4" in server.calls
    run(store, SyncOptions(BASE, KEY, False, True))
    assert "changes:/brisages:9" in server.calls


def test_own_history_is_restored_once_per_database_and_kind(store: PriceStore, server: FakeEvents) -> None:
    server.own["/brisages"] = [([event(5, 3, "AAAAAAAAAAA")], 3)]
    run(store, SyncOptions(BASE, KEY, False, True))
    run(store, SyncOptions(BASE, KEY, False, True))
    assert [call for call in server.calls if call.startswith("own:/brisages")] == ["own:/brisages:0", "own:/brisages:3"]
    assert store.connection.execute("SELECT origin, synced_at FROM broken_items").fetchall() == [
        ("local", "2026-11-16T12:00:00Z")]


def test_a_failure_is_reported_to_the_caller(store: PriceStore, server: FakeEvents) -> None:
    store.save_record(BrokenItem("Brial", 1, 2, 0.5, ((10, 3),), "2026-11-16T10:00:00Z"))
    server.failure = SyncFailure("Serveur injoignable")
    with pytest.raises(SyncFailure):
        run(store)
    assert store.connection.execute("SELECT synced_at FROM broken_items").fetchone() == (None,)


def test_the_kinds_are_the_two_planned_ones() -> None:
    assert (BROKEN.path, PET.path) == ("/brisages", "/familiers")
