"""Tests for the stoppable capture with a fake AsyncSniffer."""

import threading
from typing import Any

import pytest

from dofus_prices.capture import CaptureAborted, PacketPipeline
from dofus_prices.capture_stoppable import run_stoppable_capture


class FakeSniffer:
    """Mimics scapy's AsyncSniffer: a thread that runs until stopped or failing."""

    def __init__(self, failure: Exception | None = None, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.exception = failure
        self.running = False
        self.stop_calls = 0
        self._halt = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        if self.exception is None:
            self._halt.wait()
        self.running = False

    def start(self) -> None:
        self.running = self.exception is None
        self.thread.start()

    def stop(self) -> None:
        self.stop_calls += 1
        self._halt.set()


def make_pipeline() -> PacketPipeline:
    return PacketPipeline(lambda envelope, key: None)


def test_stops_the_sniffer_when_event_is_set() -> None:
    created: list[FakeSniffer] = []

    def factory(**kwargs: Any) -> FakeSniffer:
        created.append(FakeSniffer(**kwargs))
        return created[0]

    stop = threading.Event()
    stop.set()
    run_stoppable_capture(make_pipeline(), "eth0", stop, factory)
    assert created[0].stop_calls == 1 and not created[0].thread.is_alive()
    assert created[0].kwargs["iface"] == "eth0"


def test_sniffer_failure_is_raised() -> None:
    failure = OSError("npcap missing")
    with pytest.raises(OSError, match="npcap missing"):
        run_stoppable_capture(make_pipeline(), None, threading.Event(),
                              lambda **kwargs: FakeSniffer(failure, **kwargs))


def test_pipeline_abort_is_raised_and_stops_the_sniffer() -> None:
    pipeline = make_pipeline()
    sniffers: list[FakeSniffer] = []

    def factory(**kwargs: Any) -> FakeSniffer:
        sniffers.append(FakeSniffer(**kwargs))
        return sniffers[0]

    # run_stoppable_capture clears stale aborts first, so abort after the sniffer starts.
    original_start = FakeSniffer.start

    def start_then_abort(self: FakeSniffer) -> None:
        original_start(self)
        pipeline.abort_error = CaptureAborted("disk full")

    FakeSniffer.start = start_then_abort  # type: ignore[method-assign]
    try:
        with pytest.raises(CaptureAborted, match="disk full"):
            run_stoppable_capture(pipeline, None, threading.Event(), factory)
    finally:
        FakeSniffer.start = original_start  # type: ignore[method-assign]
    assert sniffers[0].stop_calls == 1
