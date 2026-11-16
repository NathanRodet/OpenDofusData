"""The seven day retention: the cutoff, the purge loop and the production factory."""

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from keyserver.app import build_app
from keyserver.readings_store import open_readings
from keyserver.retention import PURGE_INTERVAL_SECONDS, PURGE_RETRY_SECONDS, purge_expired, start_purge_loop
from keyserver.schemas import Reading

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
WAIT_SECONDS = 5.0


def reading(item_id: int, age: timedelta) -> Reading:
    return Reading.model_construct(server="Brial", item_id=item_id, lot_size=1, price=10, observed_at=NOW - age)


def test_purge_interval_is_one_day() -> None:
    assert PURGE_INTERVAL_SECONDS == 86_400


def test_purge_expired_uses_the_seven_day_cutoff() -> None:
    store = open_readings(":memory:")
    store.add_batch("AAAAAAAAAAA", [reading(1, timedelta(days=6, hours=23)), reading(2, timedelta(days=7, hours=1))])
    assert purge_expired(store, NOW) == 1
    assert [stored.item_id for stored in store.changes_since("BBBBBBBBBBB", 0, 10)] == [1]
    store.close()


def test_purge_loop_purges_at_start_and_stops_on_event() -> None:
    store = open_readings(":memory:")
    store.add_batch("AAAAAAAAAAA", [reading(1, timedelta(days=30))])
    stop = start_purge_loop(store, interval_seconds=0.01)
    deadline = time.monotonic() + WAIT_SECONDS
    while store.highest_seq() and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    assert store.changes_since("BBBBBBBBBBB", 0, 10) == []
    assert isinstance(stop, threading.Event)


def test_build_app_works_with_a_temporary_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KEY_SECRET", "A" * 43)
    monkeypatch.setenv("KEYSERVER_DB", str(tmp_path / "keys.db"))
    assert build_app() is not None


def test_retry_delay_is_short() -> None:
    assert PURGE_RETRY_SECONDS == 300


def test_a_failed_purge_is_retried_soon_not_after_a_full_interval() -> None:
    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        def purge_older_than(self, cutoff) -> int:
            self.calls += 1
            if self.calls == 1:
                raise sqlite3.OperationalError("database is locked")
            return 0

    flaky = Flaky()
    stop = start_purge_loop(flaky, interval_seconds=3600.0, retry_seconds=0.01)
    deadline = time.monotonic() + WAIT_SECONDS
    while flaky.calls < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    assert flaky.calls >= 2


def test_an_unexpected_error_in_a_purge_never_kills_the_loop() -> None:
    class Broken:
        def __init__(self) -> None:
            self.calls = 0

        def purge_older_than(self, cutoff) -> int:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("bug")
            return 0

    broken = Broken()
    stop = start_purge_loop(broken, interval_seconds=3600.0, retry_seconds=0.01)
    deadline = time.monotonic() + WAIT_SECONDS
    while broken.calls < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    assert broken.calls >= 2
