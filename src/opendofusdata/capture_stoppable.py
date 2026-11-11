"""Live capture that an outside thread can stop (used by the window; Scapy loaded lazily)."""

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from opendofusdata.capture import CaptureAborted, PacketPipeline, sniff_arguments

logger = logging.getLogger(__name__)

STOP_POLL_SECONDS = 0.2
START_TIMEOUT_SECONDS = 30.0
JOIN_TIMEOUT_SECONDS = 10.0
NOT_STARTED_MESSAGE = "la capture n'a pas démarré"
SnifferFactory = Callable[..., Any]
StoppableCapture = Callable[[PacketPipeline, str | None, threading.Event], None]


def _load_async_sniffer() -> SnifferFactory:
    from scapy.all import AsyncSniffer

    return AsyncSniffer


def _wait_until_started(sniffer: Any, started: threading.Event) -> bool:
    """Wait for the sniffer to really sniff; False on thread death or timeout."""
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not started.wait(STOP_POLL_SECONDS):
        if not sniffer.thread.is_alive() or time.monotonic() > deadline:
            return started.is_set()
    return True


def _wait_until_done(sniffer: Any, pipeline: PacketPipeline, stop_event: threading.Event) -> None:
    """Block until a stop is requested, the pipeline aborts or the sniffer thread ends."""
    while not stop_event.wait(STOP_POLL_SECONDS):
        if pipeline.abort_error is not None or not sniffer.thread.is_alive():
            return


def _stop_sniffer(sniffer: Any, started: threading.Event) -> None:
    """Stop a started sniffer (a stop sent before it started would be lost), then join."""
    if started.is_set() and sniffer.running:
        try:
            sniffer.stop(join=False)
        except Exception:  # Scapy_Exception, or the error that killed the sniffer
            logger.warning("sniffer stop failed", exc_info=True)
    sniffer.thread.join(JOIN_TIMEOUT_SECONDS)
    if sniffer.thread.is_alive():
        logger.warning("sniffer thread still running after %s seconds", JOIN_TIMEOUT_SECONDS)


def _start_sniffer(
    pipeline: PacketPipeline, interface: str | None, started: threading.Event,
    sniffer_factory: SnifferFactory | None,
) -> Any:
    pipeline.abort_error = None
    factory = sniffer_factory or _load_async_sniffer()
    sniffer = factory(started_callback=started.set, **sniff_arguments(pipeline, interface))
    sniffer.start()
    return sniffer


def run_stoppable_capture(
    pipeline: PacketPipeline,
    interface: str | None,
    stop_event: threading.Event,
    sniffer_factory: SnifferFactory | None = None,
) -> None:
    """Sniff Dofus traffic until stop_event is set, raising the failure that ended it.

    The sniffer error (Npcap missing, no rights) comes first, then a CaptureAborted
    recorded by the pipeline. A stop requested before the sniffer is really running is
    applied as soon as it has started.
    """
    started = threading.Event()
    sniffer = _start_sniffer(pipeline, interface, started, sniffer_factory)
    try:
        if _wait_until_started(sniffer, started):
            _wait_until_done(sniffer, pipeline, stop_event)
    finally:
        _stop_sniffer(sniffer, started)
    _raise_failure(sniffer, pipeline, started)


def _raise_failure(sniffer: Any, pipeline: PacketPipeline, started: threading.Event) -> None:
    if sniffer.exception is not None:
        raise sniffer.exception
    if not started.is_set():
        raise CaptureAborted(NOT_STARTED_MESSAGE)
    if pipeline.abort_error is not None:
        raise pipeline.abort_error
