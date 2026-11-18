"""The stream of the server: one long connection that says "something changed", so a round runs at once.

It only wakes the worker. The data still comes from the usual routes, so nothing new is trusted here, and when the
stream is not available (older server, refused, network cut) the regular rounds go on at the player's interval.
"""

import logging
import threading
import time
from collections.abc import Callable, Iterable
from typing import BinaryIO

from opendofusdata.https_json import HttpsFailure, StreamRefused, open_stream
from opendofusdata.sync_engine import SyncOptions

logger = logging.getLogger(__name__)

STREAM_PATH = "/stream"
READ_TIMEOUT_SECONDS = 30.0  # the server writes at least every 10 seconds
IDLE_SECONDS = 10.0  # nothing to listen to (no key, no address): look again
RETRY_SECONDS = 5.0
MAX_RETRY_SECONDS = 60.0
SLOW_RETRY_SECONDS = {401: 60.0, 404: 300.0, 429: 30.0}  # refused key, no stream on this server, already open
CHANGED_EVENT = "changed"
MAX_LINE_BYTES = 4096
MAX_STREAM_BYTES = 1_000_000  # one connection never reads more than this (a real one sends a few hundred bytes)
MIN_WAKE_GAP_SECONDS = 3.0  # however often the server says "changed", rounds start at most this often
Opener = Callable[[str, str, str, float], Iterable[bytes]]
LoadOptions = Callable[[], SyncOptions | None]


class StreamTooLarge(Exception):
    """A line or the whole stream is bigger than any honest server sends: the connection is dropped."""


def bounded_lines(response: BinaryIO) -> Iterable[bytes]:
    """The lines of a response read with a limit, so a server that never sends a line break cannot fill the memory."""
    total = 0
    while True:
        line = response.readline(MAX_LINE_BYTES + 1)
        if not line:
            return
        total += len(line)
        if len(line) > MAX_LINE_BYTES or total > MAX_STREAM_BYTES:
            raise StreamTooLarge
        yield line


def changed_events(lines: Iterable[bytes]) -> Iterable[str]:
    """Yield the name of every complete event of a text/event-stream (comments and heartbeats are skipped)."""
    name = ""
    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if name:
                yield name
            name = ""
        elif line.startswith("event:"):
            name = line[len("event:"):].strip()


class SyncStream:
    """A daemon thread that keeps the stream open while a key and an address exist and calls `on_change`."""

    def __init__(self, load_options: LoadOptions, on_change: Callable[[], None], opener: Opener = open_stream) -> None:
        self._load_options, self._on_change, self._opener = load_options, on_change, opener
        self._stop = threading.Event()
        self._gap_lock = threading.Lock()
        self._last_wake = float("-inf")
        self._timer: threading.Timer | None = None
        self._thread = threading.Thread(target=self._run, name="sync-stream", daemon=True)

    def start(self) -> None:
        """Start listening."""
        self._thread.start()

    def stop(self) -> None:
        """Stop listening (the thread ends at its next wake-up)."""
        self._stop.set()
        with self._gap_lock:
            if self._timer is not None:
                self._timer.cancel()

    def _changed(self) -> None:
        """Wake the worker, at most once per gap: signals that come faster are merged into one later wake-up."""
        with self._gap_lock:
            waited = time.monotonic() - self._last_wake
            if waited >= MIN_WAKE_GAP_SECONDS:
                self._last_wake = time.monotonic()
                self._on_change()
            elif self._timer is None:
                self._timer = threading.Timer(MIN_WAKE_GAP_SECONDS - waited, self._late_wake)
                self._timer.daemon = True
                self._timer.start()

    def _late_wake(self) -> None:
        with self._gap_lock:
            self._timer, self._last_wake = None, time.monotonic()
        if not self._stop.is_set():
            self._on_change()

    def _run(self) -> None:
        delay, retry = 0.0, RETRY_SECONDS
        while not self._stop.wait(delay):
            options = self._load_options()
            if options is None or not options.receive:
                delay = IDLE_SECONDS
                continue
            delay, retry = self._listen_once(options, retry)

    def _listen_once(self, options: SyncOptions, retry: float) -> tuple[float, float]:
        """One connection until it ends; returns (seconds before the next try, the next retry delay)."""
        try:
            self._read(options)
        except StreamRefused as refused:
            logger.info("flux de synchronisation refusé (HTTP %s)", refused.status)
            return SLOW_RETRY_SECONDS.get(refused.status, MAX_RETRY_SECONDS), RETRY_SECONDS
        except (HttpsFailure, OSError, StreamTooLarge) as error:
            logger.info("flux de synchronisation interrompu : %s", error)
            return retry, min(retry * 2, MAX_RETRY_SECONDS)
        return RETRY_SECONDS, RETRY_SECONDS  # a normal end (the server closes it from time to time)

    def _read(self, options: SyncOptions) -> None:
        response = self._opener(options.base_url, STREAM_PATH, options.key, READ_TIMEOUT_SECONDS)
        try:
            lines = bounded_lines(response) if hasattr(response, "readline") else response  # type: ignore[arg-type]
            for name in changed_events(lines):
                if self._stop.is_set():
                    return
                if name == CHANGED_EVENT:
                    self._changed()
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
