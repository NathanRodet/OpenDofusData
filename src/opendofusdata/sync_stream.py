"""The stream of the server: one long connection that says "something changed", so a round runs at once.

It only wakes the worker. The data still comes from the usual routes, so nothing new is trusted here, and when the
stream is not available (older server, refused, network cut) the regular rounds go on at the player's interval.
"""

import logging
import threading
from collections.abc import Callable, Iterable

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
Opener = Callable[[str, str, str, float], Iterable[bytes]]
LoadOptions = Callable[[], SyncOptions | None]


def changed_events(lines: Iterable[bytes]) -> Iterable[str]:
    """Yield the name of every complete event of a text/event-stream (comments and heartbeats are skipped)."""
    name = ""
    for raw in lines:
        line = raw[:MAX_LINE_BYTES].decode("utf-8", "replace").rstrip("\r\n")
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
        self._thread = threading.Thread(target=self._run, name="sync-stream", daemon=True)

    def start(self) -> None:
        """Start listening."""
        self._thread.start()

    def stop(self) -> None:
        """Stop listening (the thread ends at its next wake-up)."""
        self._stop.set()

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
        except (HttpsFailure, OSError) as error:
            logger.info("flux de synchronisation interrompu : %s", error)
            return retry, min(retry * 2, MAX_RETRY_SECONDS)
        return RETRY_SECONDS, RETRY_SECONDS  # a normal end (the server closes it from time to time)

    def _read(self, options: SyncOptions) -> None:
        response = self._opener(options.base_url, STREAM_PATH, options.key, READ_TIMEOUT_SECONDS)
        try:
            for name in changed_events(response):  # type: ignore[arg-type]
                if self._stop.is_set():
                    return
                if name == CHANGED_EVENT:
                    self._on_change()
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
