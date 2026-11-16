"""The synchronisation engine: send, then snapshot and changes, with progress kept after any failure."""

from datetime import datetime, timezone

import pytest

from opendofusdata import sync_engine
from opendofusdata.records import LotPrice
from opendofusdata.storage import PriceStore
from opendofusdata.sync_api import LatestPage, SyncFailure
from opendofusdata.sync_engine import DONE_MESSAGE, STATE_CURSOR, STATE_LATEST_DONE, SyncOptions, sync_once
from opendofusdata.sync_store import get_state, set_state

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
BASE = "https://sync.exemple.fr"
KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
BOTH = SyncOptions(BASE, KEY, True, True)


def remote(item_id: int, seq: int = 1, price: int = 50) -> dict[str, object]:
    return {"seq": seq, "key_id": "BBBBBBBBBBB", "server": "Brial", "item_id": item_id, "lot_size": 1,
            "price": price, "observed_at": "2026-11-16T09:00:00Z"}


class FakeServer:
    """A double of the three network calls: records what was sent, serves canned pages."""

    def __init__(self) -> None:
        self.pushed: list[list] = []
        self.latest_pages: list[LatestPage] = []
        self.change_pages: list[tuple[list, int]] = []
        self.calls: list[str] = []
        self.failure: SyncFailure | None = None
        self.fail_push_after = None
        self.fail_push_only = False
        self.failure_after_pages = None

    def push(self, base_url, key, readings):
        self.calls.append("push")
        if self.failure and (self.fail_push_only or self.fail_push_after is None):
            raise self.failure
        self.pushed.append(list(readings))
        return len(readings)

    def latest(self, base_url, key, after):
        self.calls.append(f"latest:{after}")
        if self.failure and not self.fail_push_only:
            raise self.failure
        if self.failure_after_pages is not None and len(self.latest_pages) == 0:
            raise SyncFailure("Serveur injoignable")
        return self.latest_pages.pop(0)

    def changes(self, base_url, key, since):
        self.calls.append(f"changes:{since}")
        if self.failure and not self.change_pages:
            raise self.failure
        return self.change_pages.pop(0) if self.change_pages else ([], since)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    fake = FakeServer()
    monkeypatch.setattr(sync_engine, "push_readings", fake.push)
    monkeypatch.setattr(sync_engine, "pull_latest_page", fake.latest)
    monkeypatch.setattr(sync_engine, "pull_changes", fake.changes)
    return fake


@pytest.fixture
def store() -> PriceStore:
    return PriceStore(":memory:")


def run(store: PriceStore, options: SyncOptions = BOTH):
    return sync_once(store.connection, options, clock=lambda: NOW)


def add_local(store: PriceStore, count: int) -> None:
    for number in range(count):
        store.save_lot_price(LotPrice(number + 1, "Brial", 1, 100, f"2026-11-16T10:{number % 60:02d}:00Z"))


def test_nothing_is_sent_or_pulled_when_both_options_are_off(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 3)
    outcome = run(store, SyncOptions(BASE, KEY, False, False))
    assert (outcome.sent, outcome.received, outcome.refused) == (0, 0, False)
    assert server.calls == []


def test_send_pushes_pending_rows_in_batches_and_marks_them_sent(store: PriceStore, server: FakeServer,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "SYNC_PAGE_SIZE", 2)
    add_local(store, 5)
    outcome = run(store, SyncOptions(BASE, KEY, True, False))
    assert outcome.sent == 5
    assert [len(batch) for batch in server.pushed] == [2, 2, 1]
    assert store.connection.execute("SELECT COUNT(*) FROM lot_prices WHERE synced_at IS NULL").fetchone() == (0,)


def test_failed_push_leaves_rows_unsent(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 2)
    server.failure = SyncFailure("Serveur injoignable")
    outcome = run(store, SyncOptions(BASE, KEY, True, False))
    assert (outcome.sent, outcome.refused, outcome.message) == (0, False, "Serveur injoignable")
    assert store.connection.execute("SELECT COUNT(*) FROM lot_prices WHERE synced_at IS NULL").fetchone() == (2,)


def test_receive_runs_latest_then_changes_and_stores_remote_rows_with_sender_ids(store: PriceStore,
                                                                                server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1)], 1, 4, False), LatestPage([remote(2)], 2, 4, True)]
    server.change_pages = [([remote(3, 5)], 5)]
    outcome = run(store, SyncOptions(BASE, KEY, False, True))
    assert outcome.received == 3
    assert server.calls == ["latest:0", "latest:1", "changes:4", "changes:5"]
    rows = store.connection.execute("SELECT item_id, origin, source_key_id FROM lot_prices ORDER BY item_id").fetchall()
    assert rows == [(1, "remote", "BBBBBBBBBBB"), (2, "remote", "BBBBBBBBBBB"), (3, "remote", "BBBBBBBBBBB")]


def test_cursor_starts_at_the_first_page_as_of_and_is_saved_after_each_page(store: PriceStore,
                                                                          server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1)], 1, 4, False), LatestPage([remote(2)], 2, 9, True)]
    run(store, SyncOptions(BASE, KEY, False, True))
    assert get_state(store.connection, STATE_LATEST_DONE) == "1"
    assert get_state(store.connection, STATE_CURSOR) == "4"
    server.change_pages = [([remote(3, 5)], 5), ([remote(4, 6)], 6)]
    run(store, SyncOptions(BASE, KEY, False, True))
    assert get_state(store.connection, STATE_CURSOR) == "6"


def test_second_run_pulls_only_new_changes(store: PriceStore, server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1)], 1, 4, True)]
    run(store, SyncOptions(BASE, KEY, False, True))
    server.calls.clear()
    run(store, SyncOptions(BASE, KEY, False, True))
    assert server.calls == ["changes:4"]


def test_401_stops_everything_and_reports_refused(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 1)
    server.failure = SyncFailure("Clé refusée ou révoquée", refused=True)
    outcome = run(store)
    assert (outcome.refused, outcome.message) == (True, "Clé refusée ou révoquée")
    assert server.calls == ["push"]


def test_network_error_keeps_the_progress_made(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 1)
    server.latest_pages = [LatestPage([remote(1)], 1, 4, True)]
    server.change_pages = []
    server.failure = None
    first = run(store)
    assert first.received == 1 and first.sent == 1
    server.failure = SyncFailure("Serveur injoignable")
    second = run(store)
    assert second.message == "Serveur injoignable"
    assert get_state(store.connection, STATE_CURSOR) == "4"


def test_received_rows_are_not_sent_back(store: PriceStore, server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1), remote(2)], 2, 2, True)]
    run(store)
    assert server.pushed == []


def test_a_cursor_that_does_not_advance_is_refused(store: PriceStore, server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1)], 0, 4, False)]
    outcome = run(store, SyncOptions(BASE, KEY, False, True))
    assert outcome.message != "" and not outcome.refused
    assert get_state(store.connection, STATE_LATEST_DONE) is None


def test_a_failed_send_does_not_block_receiving(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 1)
    server.failure = SyncFailure("Le serveur a refusé des relevés (vérifie l'heure de ton PC)")
    server.latest_pages = [LatestPage([remote(1)], 1, 4, True)]
    server.fail_push_only = True
    outcome = run(store)
    assert outcome.received == 1 and outcome.sent == 0
    assert "heure" in outcome.message and not outcome.refused


def test_a_refused_key_during_send_still_stops_everything(store: PriceStore, server: FakeServer) -> None:
    add_local(store, 1)
    server.failure = SyncFailure("Clé refusée ou révoquée", refused=True)
    server.fail_push_only = True
    server.latest_pages = [LatestPage([remote(1)], 1, 4, True)]
    outcome = run(store)
    assert outcome.refused is True and outcome.received == 0
    assert not any(call.startswith("latest") for call in server.calls)


def test_receive_loops_are_capped(store: PriceStore, server: FakeServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_engine, "MAX_SYNC_PAGES", 3)
    server.latest_pages = [LatestPage([remote(number)], number, 4, False) for number in range(1, 10)]
    outcome = run(store, SyncOptions(BASE, KEY, False, True))
    assert outcome.message != DONE_MESSAGE and not outcome.refused
    assert len(server.calls) == 3


def test_an_interrupted_snapshot_resumes_where_it_stopped(store: PriceStore, server: FakeServer) -> None:
    server.latest_pages = [LatestPage([remote(1)], 7, 4, False)]
    server.failure_after_pages = 1
    first = run(store, SyncOptions(BASE, KEY, False, True))
    assert first.message != DONE_MESSAGE
    server.failure_after_pages = None
    server.calls.clear()
    server.latest_pages = [LatestPage([remote(2)], 8, 99, True)]
    run(store, SyncOptions(BASE, KEY, False, True))
    assert server.calls[0] == "latest:7"
    assert get_state(store.connection, STATE_CURSOR) == "4"  # the as_of of the FIRST page, not the last


def test_a_garbled_cursor_falls_back_to_a_fresh_snapshot(store: PriceStore, server: FakeServer) -> None:
    set_state(store.connection, STATE_CURSOR, "abc")
    set_state(store.connection, STATE_LATEST_DONE, "1")
    server.latest_pages = [LatestPage([remote(1)], 1, 4, True)]
    outcome = run(store, SyncOptions(BASE, KEY, False, True))
    assert outcome.message == DONE_MESSAGE
    assert server.calls[0] == "latest:0"
    assert get_state(store.connection, STATE_CURSOR) == "4"
