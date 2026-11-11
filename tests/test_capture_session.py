"""Tests for the capture session controller with fake capture functions."""

import threading
import time
from datetime import datetime, timezone

import pytest

from opendofusdata.capture import CaptureAborted, PacketPipeline
from opendofusdata.capture_session import CaptureSession, CaptureStatus
from opendofusdata.categories import CategorySettings
from opendofusdata.log_feed import LogFeed
from opendofusdata.storage import PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope, stats_envelope

MOMENT = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
WAIT_SECONDS = 5.0


def fixed_now() -> datetime:
    return MOMENT


def wait_for(condition) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "timeout"
        time.sleep(0.01)


def feeding_capture(pipeline: PacketPipeline, interface: str | None, stop: threading.Event) -> None:
    pipeline.on_envelope(lot_envelope(), FLOW_KEY)
    pipeline.on_envelope(stats_envelope(), FLOW_KEY)
    stop.wait(WAIT_SECONDS)


def make_session(tmp_path, capture) -> CaptureSession:
    return CaptureSession(str(tmp_path / "test.db"), "Brial", None, capture, fixed_now)


def test_initial_state_is_stopped(tmp_path) -> None:
    snapshot = make_session(tmp_path, feeding_capture).snapshot()
    assert snapshot.status is CaptureStatus.STOPPED
    assert (snapshot.server, snapshot.price_count, snapshot.stats_count) == ("Brial", 0, 0)
    assert snapshot.last_record_at is None and snapshot.error_message is None


def test_counts_records_and_saves_them_on_stop(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    session.start()
    wait_for(lambda: session.snapshot().stats_count > 0)
    assert session.snapshot().status is CaptureStatus.RUNNING
    session.stop()
    snapshot = session.snapshot()
    assert snapshot.status is CaptureStatus.STOPPED
    assert snapshot.price_count > 0 and snapshot.last_record_at == MOMENT
    store = PriceStore(str(tmp_path / "test.db"))
    try:
        assert len(store.latest_prices()) == snapshot.price_count
    finally:
        store.close()


def test_stop_is_idempotent_and_safe_before_start(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    session.stop()
    session.start()
    session.stop()
    session.stop()
    assert session.snapshot().status is CaptureStatus.STOPPED


def test_start_twice_runs_one_capture(tmp_path) -> None:
    calls: list[int] = []

    def capture(pipeline, interface, stop) -> None:
        calls.append(1)
        stop.wait(WAIT_SECONDS)

    session = make_session(tmp_path, capture)
    session.start()
    session.start()
    session.stop()
    assert calls == [1]


def test_restart_after_stop_keeps_counters(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    session.start()
    wait_for(lambda: session.snapshot().stats_count > 0)
    session.stop()
    first = session.snapshot().price_count
    session.start()
    wait_for(lambda: session.snapshot().price_count == 2 * first)
    session.stop()
    assert session.snapshot().status is CaptureStatus.STOPPED


@pytest.mark.parametrize("error, expected", [
    (RuntimeError("no npcap"), "no npcap"),
    (CaptureAborted("disque plein"), "disque plein"),
])
def test_capture_errors_become_error_status(tmp_path, error, expected) -> None:
    def failing(pipeline, interface, stop) -> None:
        raise error

    session = make_session(tmp_path, failing)
    session.start()
    wait_for(lambda: session.snapshot().status is CaptureStatus.ERROR)
    assert expected in session.snapshot().error_message
    session.stop()


def test_error_is_cleared_by_a_successful_restart(tmp_path) -> None:
    outcomes = [RuntimeError("boom"), None]

    def capture(pipeline, interface, stop) -> None:
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome
        stop.wait(WAIT_SECONDS)

    session = make_session(tmp_path, capture)
    session.start()
    wait_for(lambda: session.snapshot().status is CaptureStatus.ERROR)
    session.start()
    assert session.snapshot().error_message is None
    session.stop()
    assert session.snapshot().status is CaptureStatus.STOPPED


def test_unopenable_database_gives_error_without_thread(tmp_path) -> None:
    session = CaptureSession(str(tmp_path / "missing" / "x.db"), "Brial", None, feeding_capture, fixed_now)
    session.start()
    snapshot = session.snapshot()
    assert snapshot.status is CaptureStatus.ERROR and "base de données" in snapshot.error_message
    session.stop()


def test_request_stop_is_non_blocking_and_ends_stopped(tmp_path) -> None:
    release = threading.Event()

    def slow_capture(pipeline, interface, stop) -> None:
        stop.wait(WAIT_SECONDS)
        release.wait(WAIT_SECONDS)

    session = make_session(tmp_path, slow_capture)
    session.start()
    session.request_stop()
    assert session.snapshot().status is CaptureStatus.STOPPING
    session.start()  # ignored while stopping
    release.set()
    wait_for(lambda: session.snapshot().status is CaptureStatus.STOPPED)


def test_stop_timeout_becomes_an_error(tmp_path) -> None:
    release = threading.Event()
    clock = [0.0]

    def stuck_capture(pipeline, interface, stop) -> None:
        release.wait(WAIT_SECONDS)

    session = CaptureSession(str(tmp_path / "t.db"), "Brial", None, stuck_capture, fixed_now,
                             monotonic=lambda: clock[0], stop_timeout=10.0)
    session.start()
    session.request_stop()
    assert session.snapshot().status is CaptureStatus.STOPPING
    clock[0] = 11.0
    snapshot = session.snapshot()
    assert snapshot.status is CaptureStatus.ERROR and "trop de temps" in snapshot.error_message
    release.set()
    wait_for(lambda: session.snapshot().status is CaptureStatus.STOPPED)


def test_status_is_final_even_if_the_writer_fails_to_stop(tmp_path) -> None:
    class BrokenWriter:
        def submit(self, record) -> None:
            pass

        def stop(self) -> None:
            raise OSError("disk gone")

    session = CaptureSession(str(tmp_path / "b.db"), "Brial", None, feeding_capture, fixed_now,
                             writer_factory=lambda path: BrokenWriter())
    session.start()
    wait_for(lambda: session.snapshot().stats_count > 0)
    session.stop()
    wait_for(lambda: session.snapshot().status is CaptureStatus.ERROR)
    assert "disk gone" in session.snapshot().error_message


def test_disabled_hdv_records_are_not_counted_or_stored(tmp_path) -> None:
    ran = threading.Event()

    def capture(pipeline, interface, stop) -> None:
        feeding_capture_once(pipeline)
        ran.set()
        stop.wait(WAIT_SECONDS)

    session = CaptureSession(str(tmp_path / "test.db"), "Brial", None, capture, fixed_now,
                             categories=CategorySettings([]))
    session.start()
    wait_for(ran.is_set)
    session.stop()
    snapshot = session.snapshot()
    assert (snapshot.price_count, snapshot.stats_count) == (0, 0)
    store = PriceStore(str(tmp_path / "test.db"))
    try:
        assert store.latest_prices() == []
    finally:
        store.close()


def feeding_capture_once(pipeline: PacketPipeline) -> None:
    pipeline.on_envelope(lot_envelope(), FLOW_KEY)
    pipeline.on_envelope(stats_envelope(), FLOW_KEY)


def test_enabled_records_reach_the_feed_when_visible(tmp_path) -> None:
    feed = LogFeed()
    feed.set_visible(True)
    session = CaptureSession(str(tmp_path / "test.db"), "Brial", None, feeding_capture, fixed_now, feed=feed)
    session.start()
    wait_for(lambda: len(feed.entries()) > 0)
    session.stop()
    assert feed.entries()[0].category == "HDV"


def test_apply_settings_while_running_keeps_active_server_until_restart(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    session.start()
    session.apply_settings(str(tmp_path / "other.db"), "Kourial")
    assert session.snapshot().server == "Brial"
    session.stop()
    session.start()
    assert session.snapshot().server == "Kourial"
    session.stop()


def test_apply_settings_new_database_used_on_next_start(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    new_path = str(tmp_path / "other.db")
    session.apply_settings(new_path, "Brial")
    session.start()
    wait_for(lambda: session.snapshot().stats_count > 0)
    session.stop()
    store = PriceStore(new_path)
    try:
        assert len(store.latest_prices()) > 0
    finally:
        store.close()


def test_unwritable_database_after_apply_gives_error_snapshot(tmp_path) -> None:
    session = make_session(tmp_path, feeding_capture)
    session.apply_settings(str(tmp_path / "missing_folder" / "x.db"), "Brial")
    session.start()
    snapshot = session.snapshot()
    assert snapshot.status is CaptureStatus.ERROR and "x.db" in (snapshot.error_message or "")
