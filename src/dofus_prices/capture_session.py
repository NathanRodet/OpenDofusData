"""Capture session controller: runs a live capture in a thread (no GUI, testable)."""

import logging
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dofus_prices.capture import CaptureAborted, PacketPipeline
from dofus_prices.capture_errors import CAPTURE_FAILED_MESSAGE
from dofus_prices.capture_stoppable import StoppableCapture
from dofus_prices.run_pipeline import Clock, make_envelope_handler
from dofus_prices.session_counters import CountingWriter, SessionCounters
from dofus_prices.storage import StoreWriter

logger = logging.getLogger(__name__)

STOP_JOIN_TIMEOUT_SECONDS = 15.0
ABORTED_MESSAGE = "Capture interrompue ({error})."
DATABASE_FAILED_MESSAGE = "Impossible d'ouvrir la base de données {path} : {error}"
WriterFactory = Callable[[str], StoreWriter]


class CaptureStatus(Enum):
    """Lifecycle state of a capture session."""

    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


@dataclass(frozen=True)
class SessionSnapshot:
    """A consistent view of the session for display."""

    status: CaptureStatus
    server: str
    price_count: int
    stats_count: int
    last_record_at: datetime | None
    error_message: str | None


class CaptureSession:
    """Starts and stops a capture in a background thread; counters survive restarts."""

    def __init__(
        self, database_path: str, server: str, interface: str | None, capture: StoppableCapture,
        now: Clock, writer_factory: WriterFactory = StoreWriter,
    ) -> None:
        self._settings = (database_path, server, interface)
        self._capture, self._now, self._writer_factory = capture, now, writer_factory
        self._counters = SessionCounters()
        self._lock = threading.Lock()
        self._status, self._error = CaptureStatus.STOPPED, None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def snapshot(self) -> SessionSnapshot:
        """Return the current status, counters and last error message."""
        prices, stats, last_record_at = self._counters.read()
        with self._lock:
            return SessionSnapshot(self._status, self._settings[1], prices, stats,
                                   last_record_at, self._error)

    def start(self) -> None:
        """Start capturing; does nothing while already running."""
        with self._lock:
            if self._status is CaptureStatus.RUNNING:
                return
            writer = self._open_writer()
            if writer is None:
                return
            self._stop_event = threading.Event()
            self._status, self._error = CaptureStatus.RUNNING, None
            self._thread = threading.Thread(target=self._run, args=(writer, self._stop_event),
                                            name="capture-session", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the capture, wait for the thread and flush the writer; safe to repeat."""
        with self._lock:
            thread, event = self._thread, self._stop_event
        event.set()
        if thread is not None:
            thread.join(STOP_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                logger.warning("capture thread still running after %s seconds", STOP_JOIN_TIMEOUT_SECONDS)

    def _open_writer(self) -> StoreWriter | None:
        path = self._settings[0]
        try:
            return self._writer_factory(path)
        except (sqlite3.Error, OSError) as error:
            self._status = CaptureStatus.ERROR
            self._error = DATABASE_FAILED_MESSAGE.format(path=path, error=error)
            return None

    def _run(self, writer: StoreWriter, stop_event: threading.Event) -> None:
        _, server, interface = self._settings
        counting = CountingWriter(writer, self._counters, self._now)
        pipeline = PacketPipeline(make_envelope_handler(counting, server, self._now))
        error = self._capture_error(pipeline, interface, stop_event)
        writer.stop()
        with self._lock:
            self._status = CaptureStatus.STOPPED if error is None else CaptureStatus.ERROR
            self._error = error

    def _capture_error(
        self, pipeline: PacketPipeline, interface: str | None, stop_event: threading.Event
    ) -> str | None:
        try:
            self._capture(pipeline, interface, stop_event)
        except CaptureAborted as error:
            return ABORTED_MESSAGE.format(error=error)
        # scapy raises several unrelated types when Npcap or the interface is unusable.
        except Exception as error:
            logger.exception("capture failure")
            return CAPTURE_FAILED_MESSAGE.format(error=error)
        return None
