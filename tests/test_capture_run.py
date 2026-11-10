"""Tests for run_capture against a fake sniff honouring Scapy's real contract."""

from collections.abc import Callable
from typing import Any

import pytest

from dofus_prices.capture import BPF_FILTER, CaptureAborted, PacketPipeline, run_capture
from tests.test_capture import frame, segment


class FakeSniff:
    """Mimics scapy.sendrecv.sniff: swallows prn errors, honours stop_filter and chainCC."""

    def __init__(self, packets: list[Any], interrupt: bool = False) -> None:
        self.packets = packets
        self.interrupt = interrupt
        self.kwargs: dict[str, Any] = {}

    def __call__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        try:
            self._run(kwargs["prn"], kwargs.get("stop_filter"))
        except KeyboardInterrupt:
            if kwargs.get("chainCC", False):
                raise

    def _run(self, prn: Callable[[Any], Any], stop_filter: Callable[[Any], bool] | None) -> None:
        if self.interrupt:
            raise KeyboardInterrupt
        for packet in self.packets:
            try:
                prn(packet)
            except Exception:
                return  # Scapy closes the failed socket and sniff returns normally
            if stop_filter and stop_filter(packet):
                return


def aborting_pipeline() -> PacketPipeline:
    def aborting(envelope, key) -> None:
        raise CaptureAborted("disk full")

    return PacketPipeline(aborting)


def test_callback_abort_ends_run_capture_with_capture_aborted() -> None:
    fake = FakeSniff([segment(1000, frame("Demo", b"x"))])
    with pytest.raises(CaptureAborted, match="disk full"):
        run_capture(aborting_pipeline(), sniff_function=fake)


def test_stop_filter_turns_true_once_the_pipeline_aborted() -> None:
    packet = segment(1000, frame("Demo", b"x"))
    pipeline = aborting_pipeline()
    fake = FakeSniff([])
    run_capture(pipeline, sniff_function=fake)
    assert fake.kwargs["stop_filter"](packet) is False
    with pytest.raises(CaptureAborted):
        pipeline.handle_packet(packet)
    assert fake.kwargs["stop_filter"](packet) is True


def test_keyboard_interrupt_propagates_with_chain_cc() -> None:
    fake = FakeSniff([], interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        run_capture(PacketPipeline(lambda envelope, key: None), sniff_function=fake)


def test_sniff_is_called_with_the_expected_arguments() -> None:
    pipeline = PacketPipeline(lambda envelope, key: None)
    fake = FakeSniff([])
    run_capture(pipeline, "Ethernet", sniff_function=fake)
    assert fake.kwargs["filter"] == BPF_FILTER
    assert fake.kwargs["store"] is False
    assert fake.kwargs["chainCC"] is True
    assert fake.kwargs["iface"] == "Ethernet"
    assert fake.kwargs["prn"] == pipeline.handle_packet
    assert callable(fake.kwargs["stop_filter"])
    assert fake.kwargs["stop_filter"](object()) is False


def test_stale_abort_state_does_not_stop_a_new_capture() -> None:
    pipeline = PacketPipeline(lambda envelope, key: None)
    pipeline.abort_error = CaptureAborted("from an earlier run")
    fake = FakeSniff([])
    run_capture(pipeline, sniff_function=fake)
    assert pipeline.abort_error is None
    assert fake.kwargs["stop_filter"](object()) is False
