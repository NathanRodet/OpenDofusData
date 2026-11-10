"""Live capture that an outside thread can stop (used by the window; Scapy loaded lazily)."""

import logging
import threading
from collections.abc import Callable
from typing import Any

from dofus_prices.capture import PacketPipeline, sniff_arguments

logger = logging.getLogger(__name__)

STOP_POLL_SECONDS = 0.2
SnifferFactory = Callable[..., Any]
StoppableCapture = Callable[[PacketPipeline, str | None, threading.Event], None]


def _load_async_sniffer() -> SnifferFactory:
    from scapy.all import AsyncSniffer

    return AsyncSniffer


def _wait_until_done(sniffer: Any, pipeline: PacketPipeline, stop_event: threading.Event) -> None:
    """Block until a stop is requested, the pipeline aborts or the sniffer thread ends."""
    while not stop_event.wait(STOP_POLL_SECONDS):
        if pipeline.abort_error is not None or not sniffer.thread.is_alive():
            return


def _stop_sniffer(sniffer: Any) -> None:
    if sniffer.running:
        sniffer.stop()
    sniffer.thread.join()


def run_stoppable_capture(
    pipeline: PacketPipeline,
    interface: str | None,
    stop_event: threading.Event,
    sniffer_factory: SnifferFactory | None = None,
) -> None:
    """Sniff Dofus traffic until stop_event is set, raising the failure that ended it.

    A CaptureAborted recorded by the pipeline, or an error raised inside the sniffer
    thread (Npcap missing, no rights), is re-raised once the sniffer has stopped.
    """
    pipeline.abort_error = None
    factory = sniffer_factory or _load_async_sniffer()
    sniffer = factory(**sniff_arguments(pipeline, interface))
    sniffer.start()
    try:
        _wait_until_done(sniffer, pipeline, stop_event)
    finally:
        _stop_sniffer(sniffer)
    if sniffer.exception is not None:
        raise sniffer.exception
    if pipeline.abort_error is not None:
        raise pipeline.abort_error
