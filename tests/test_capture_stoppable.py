"""Tests for the stoppable capture with fake AsyncSniffers."""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

from opendofusdata import capture_stoppable
from opendofusdata.capture import CaptureAborted, PacketPipeline
from opendofusdata.capture_stoppable import run_stoppable_capture

SLOW_START_SECONDS = 0.5


class FakeSniffer:
    """Mimics AsyncSniffer: `running` is set at once, but a stop only works once started."""

    def __init__(self, started_callback: Callable[[], None], start_delay: float = 0.0,
                 failure: Exception | None = None, stop_failure: Exception | None = None,
                 error_on_stop: Exception | None = None,
                 **kwargs: Any) -> None:
        self.kwargs, self.exception, self.stop_failure = kwargs, failure, stop_failure
        self.started_callback, self.start_delay = started_callback, start_delay
        self.running, self.stop_calls = False, 0
        self.stopped_before_start, self.error_on_stop = False, error_on_stop
        self.sniffing = threading.Event()
        self._halt = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        self.running = True
        time.sleep(self.start_delay)
        if self.exception is not None:
            self.running = False
            return
        self.sniffing.set()
        self.started_callback()
        self._halt.wait()
        self.running = False

    def start(self) -> None:
        self.thread.start()

    def stop(self, join: bool = True) -> None:
        self.stop_calls += 1
        self.stopped_before_start = not self.sniffing.is_set()
        if self.error_on_stop is not None:
            self.exception = self.error_on_stop
        if self.stop_failure is not None:
            raise self.stop_failure
        self._halt.set()


def make_pipeline() -> PacketPipeline:
    return PacketPipeline(lambda envelope, key: None)


def run_with(stop: threading.Event, pipeline: PacketPipeline | None = None, **options: Any) -> FakeSniffer:
    created: list[FakeSniffer] = []

    def factory(**kwargs: Any) -> FakeSniffer:
        created.append(FakeSniffer(**options, **kwargs))
        return created[0]

    run_stoppable_capture(pipeline or make_pipeline(), "eth0", stop, factory)
    return created[0]


def test_stops_the_sniffer_when_event_is_set() -> None:
    stop = threading.Event()
    stop.set()
    sniffer = run_with(stop)
    assert sniffer.stop_calls == 1
    assert not sniffer.thread.is_alive()
    assert sniffer.kwargs["iface"] == "eth0"


def test_stop_requested_during_slow_start_waits_for_the_start() -> None:
    stop = threading.Event()
    stop.set()
    sniffer = run_with(stop, start_delay=SLOW_START_SECONDS)
    assert sniffer.stop_calls == 1
    assert not sniffer.stopped_before_start
    assert not sniffer.thread.is_alive()


def test_sniffer_failure_is_raised() -> None:
    with pytest.raises(OSError, match="npcap missing"):
        run_with(threading.Event(), failure=OSError("npcap missing"))


def test_sniffer_error_wins_over_a_failing_stop() -> None:
    stop = threading.Event()
    stop.set()
    with pytest.raises(RuntimeError, match="real npcap error"):
        run_with(stop, stop_failure=ValueError("stop broke"),
                 error_on_stop=RuntimeError("real npcap error"))


def test_unusable_stop_without_sniffer_error_is_only_logged(caplog) -> None:
    stop = threading.Event()
    stop.set()
    sniffer = run_with(stop, stop_failure=ValueError("stop broke"))
    assert sniffer.stop_calls == 1
    assert "sniffer stop failed" in caplog.text


def test_never_started_sniffer_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(capture_stoppable, "START_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(capture_stoppable, "JOIN_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(CaptureAborted):
        run_with(threading.Event(), start_delay=2 * SLOW_START_SECONDS)


def test_pipeline_abort_is_raised_and_stops_the_sniffer(monkeypatch) -> None:
    pipeline = make_pipeline()
    sniffers: list[FakeSniffer] = []

    def factory(**kwargs: Any) -> FakeSniffer:
        sniffer = FakeSniffer(**kwargs)
        original_start = sniffer.start

        def start_then_abort() -> None:
            original_start()
            sniffer.sniffing.wait(1.0)
            pipeline.abort_error = CaptureAborted("disk full")

        monkeypatch.setattr(sniffer, "start", start_then_abort)
        sniffers.append(sniffer)
        return sniffer

    with pytest.raises(CaptureAborted, match="disk full"):
        run_stoppable_capture(pipeline, None, threading.Event(), factory)
    assert sniffers[0].stop_calls == 1


@pytest.fixture(autouse=True)
def short_join_timeout(monkeypatch) -> None:
    monkeypatch.setattr(capture_stoppable, "JOIN_TIMEOUT_SECONDS", 0.2)
