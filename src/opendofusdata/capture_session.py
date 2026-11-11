"""Capture session controller: runs a live capture in a thread (no GUI, testable)."""

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from opendofusdata.capture import CaptureAborted, PacketPipeline
from opendofusdata.capture_errors import CAPTURE_FAILED_MESSAGE
from opendofusdata.capture_stoppable import StoppableCapture
from opendofusdata.categories import DEFAULT_ENABLED, CategorySettings, FilteringWriter
from opendofusdata.log_feed import FeedWriter, LogFeed
from opendofusdata.run_pipeline import Clock, make_envelope_handler
from opendofusdata.session_counters import CountingWriter, SessionCounters
from opendofusdata.storage import StoreWriter

logger = logging.getLogger(__name__)

STOP_TIMEOUT_SECONDS = 15.0
ABORTED_MESSAGE = "Capture interrompue ({error})."
DATABASE_FAILED_MESSAGE = "Impossible d'ouvrir la base de données {path} : {error}"
STOP_TIMEOUT_MESSAGE = "L'arrêt de la capture prend trop de temps. Fermez puis relancez l'outil."
WRITER_FAILED_MESSAGE = "Les derniers enregistrements n'ont pas pu être écrits ({error})."
WriterFactory = Callable[[str], StoreWriter]
Monotonic = Callable[[], float]


class CaptureStatus(Enum):
    """Lifecycle state of a capture session."""

    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(frozen=True)
class SessionSnapshot:
    """The session state read under one lock, for display.

    The counters count records handed to the writer queue; the writer saves them
    right after, and everything queued is flushed when the capture stops.
    """

    status: CaptureStatus
    server: str
    price_count: int
    stats_count: int
    last_record_at: datetime | None
    error_message: str | None
    recycling_count: int = 0
    pet_count: int = 0
    breaking_count: int = 0


class CaptureSession:
    """Starts and stops a capture in a background thread; counters survive restarts."""

    def __init__(
        self, database_path: str, server: str, interface: str | None, capture: StoppableCapture,
        now: Clock, writer_factory: WriterFactory = StoreWriter,
        monotonic: Monotonic = time.monotonic, stop_timeout: float = STOP_TIMEOUT_SECONDS,
        categories: CategorySettings | None = None, feed: LogFeed | None = None,
    ) -> None:
        self._settings = (database_path, server, interface)
        self._pending: tuple[str, str] | None = None
        self.categories = categories if categories is not None else CategorySettings(DEFAULT_ENABLED)
        self.feed = feed if feed is not None else LogFeed()
        self._capture, self._now, self._writer_factory = capture, now, writer_factory
        self._monotonic, self._stop_timeout = monotonic, stop_timeout
        self._counters = SessionCounters()
        self._lock = threading.Lock()
        self._status, self._error = CaptureStatus.STOPPED, None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._stop_deadline = 0.0

    def snapshot(self) -> SessionSnapshot:
        """Return the state; a stop that exceeds its timeout becomes an error."""
        with self._lock:
            if self._status is CaptureStatus.STOPPING and self._monotonic() > self._stop_deadline:
                self._status, self._error = CaptureStatus.ERROR, STOP_TIMEOUT_MESSAGE
            prices, stats, last_record_at = self._counters.read()
            return SessionSnapshot(self._status, self._settings[1], prices, stats,
                                   last_record_at, self._error, self._counters.recycling_count(),
                                   self._counters.pet_count(), self._counters.breaking_count())

    @property
    def database_path(self) -> str:
        """The database of the current (or next, once started) capture."""
        with self._lock:
            return self._pending[0] if self._pending is not None else self._settings[0]

    @property
    def server(self) -> str:
        """The server of the current (or next, once started) capture."""
        with self._lock:
            return self._pending[1] if self._pending is not None else self._settings[1]

    def apply_settings(self, database_path: str, server: str) -> None:
        """Choose the database and server of the next capture; a running one is not touched."""
        with self._lock:
            self._pending = (database_path, server)

    def _promote_pending_settings(self) -> None:
        if self._pending is not None:
            self._settings = (*self._pending, self._settings[2])
            self._pending = None

    def start(self) -> None:
        """Start capturing; does nothing while a capture is running or stopping."""
        with self._lock:
            if self._status in (CaptureStatus.RUNNING, CaptureStatus.STOPPING):
                return
            self._promote_pending_settings()
            writer = self._open_writer()
            if writer is None:
                return
            self._stop_event = threading.Event()
            self._status, self._error = CaptureStatus.RUNNING, None
            self._thread = threading.Thread(target=self._run, args=(writer, self._stop_event),
                                            name="capture-session", daemon=True)
            self._thread.start()

    def request_stop(self) -> None:
        """Ask the capture to stop without waiting (status STOPPING until it ends)."""
        with self._lock:
            if self._status is CaptureStatus.RUNNING:
                self._status = CaptureStatus.STOPPING
                self._stop_deadline = self._monotonic() + self._stop_timeout
            self._stop_event.set()

    def stop(self) -> None:
        """Stop the capture and wait (bounded) for the thread; safe to repeat."""
        self.request_stop()
        thread = self._thread
        if thread is not None:
            thread.join(self._stop_timeout)
        self.snapshot()

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
        sink = FilteringWriter(FeedWriter(CountingWriter(writer, self._counters, self._now),
                                          self.feed, self._now), self.categories)
        pipeline = PacketPipeline(make_envelope_handler(sink, server, self._now))
        error = None
        try:
            error = self._capture_error(pipeline, interface, stop_event)
        finally:
            self._finish(self._stop_writer(writer, error))

    def _stop_writer(self, writer: StoreWriter, error: str | None) -> str | None:
        """Flush and close the writer; a failure here is reported unless one is already."""
        try:
            writer.stop()
        except (sqlite3.Error, OSError) as failure:
            logger.exception("writer stop failed")
            return error or WRITER_FAILED_MESSAGE.format(error=failure)
        return error

    def _finish(self, error: str | None) -> None:
        with self._lock:
            self._status = CaptureStatus.STOPPED if error is None else CaptureStatus.ERROR
            self._error = error

    def _capture_error(
        self, pipeline: PacketPipeline, interface: str | None, stop_event: threading.Event
    ) -> str | None:
        try:
            self._capture(pipeline, interface, stop_event)
        except CaptureAborted as error:
            logger.warning("capture aborted: %s", error)
            return ABORTED_MESSAGE.format(error=error)
        # scapy raises several unrelated types when Npcap or the interface is unusable.
        except Exception as error:
            logger.exception("capture failure")
            return CAPTURE_FAILED_MESSAGE.format(error=error)
        return None
