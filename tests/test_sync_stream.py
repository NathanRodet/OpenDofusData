"""The stream listener: it wakes the worker on 'changed', and backs off when the stream is refused or cut."""

import threading
import time

import pytest

from opendofusdata.https_json import HttpsFailure, StreamRefused
from opendofusdata.sync_engine import SyncOptions
from opendofusdata.sync_stream import SyncStream, changed_events

OPTIONS = SyncOptions("https://server.example.fr", "odk1.key", True, True, 30)
WAIT_SECONDS = 5.0


def test_only_complete_changed_events_are_reported_and_heartbeats_are_skipped() -> None:
    lines = [b"retry: 5000\n", b"event: ready\n", b"data: {}\n", b"\n", b": keepalive\n", b"\n",
             b"event: changed\n", b'data: ["readings"]\n', b"\n", b"event: changed\n"]  # the last one is cut short
    assert list(changed_events(lines)) == ["ready", "changed"]


def test_a_very_long_line_is_cut_and_never_breaks_the_parser() -> None:
    assert list(changed_events([b"data: " + b"x" * 100_000 + b"\n", b"\n"])) == []


def make_stream(opener, wakes: list[int], options=OPTIONS) -> SyncStream:
    return SyncStream(lambda: options, lambda: wakes.append(1), opener)


def test_each_changed_event_wakes_the_worker_once(monkeypatch) -> None:
    from opendofusdata import sync_stream

    monkeypatch.setattr(sync_stream, "MIN_WAKE_GAP_SECONDS", 0.0)
    wakes: list[int] = []
    stream = make_stream(lambda *args: [b"event: changed\n", b"\n", b"event: ready\n", b"\n", b"event: changed\n", b"\n"],
                         wakes)
    stream._read(OPTIONS)
    assert wakes == [1, 1]


def test_a_refused_stream_waits_longer_depending_on_the_reason() -> None:
    def refuse(status: int):
        def opener(*args):
            raise StreamRefused(status)
        return opener

    waits = {status: make_stream(refuse(status), [])._listen_once(OPTIONS, 5.0)[0] for status in (401, 404, 429, 500)}
    assert waits == {401: 60.0, 404: 300.0, 429: 30.0, 500: 60.0}


def test_a_network_failure_retries_with_a_doubling_delay_up_to_a_minute() -> None:
    def cut(*args):
        raise HttpsFailure("unreachable")

    stream = make_stream(cut, [])
    assert stream._listen_once(OPTIONS, 5.0) == (5.0, 10.0)
    assert stream._listen_once(OPTIONS, 40.0) == (40.0, 60.0)


def test_the_thread_listens_while_there_are_options_and_stops_on_request() -> None:
    wakes: list[int] = []
    woken = threading.Event()

    def opener(*args):
        woken.set()
        return [b"event: changed\n", b"\n"]

    stream = SyncStream(lambda: OPTIONS, lambda: wakes.append(1), opener)
    stream.start()
    assert woken.wait(WAIT_SECONDS)
    stream.stop()
    stream._thread.join(WAIT_SECONDS)
    assert wakes and not stream._thread.is_alive()


def test_without_a_key_nothing_is_opened() -> None:
    opened: list[int] = []
    stream = SyncStream(lambda: None, lambda: None, lambda *args: opened.append(1) or [])
    stream.start()
    stream.stop()
    stream._thread.join(WAIT_SECONDS)
    assert opened == []


def test_signals_that_come_too_fast_are_merged_into_one_later_wake_up(monkeypatch) -> None:
    from opendofusdata import sync_stream

    monkeypatch.setattr(sync_stream, "MIN_WAKE_GAP_SECONDS", 0.2)
    wakes: list[float] = []
    stream = SyncStream(lambda: None, lambda: wakes.append(time.monotonic()), lambda *args: [])
    for _ in range(50):
        stream._changed()
    time.sleep(0.5)
    stream.stop()
    assert len(wakes) == 2 and wakes[1] - wakes[0] >= 0.15
