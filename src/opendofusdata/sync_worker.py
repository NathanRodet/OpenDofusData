"""The background worker: one synchronisation round per interval, slowing down while the server is unreachable."""

import logging
import sqlite3
import threading
from collections.abc import Callable

from opendofusdata.storage import PriceStore
from opendofusdata.sync_engine import DONE_MESSAGE, SyncOptions, SyncOutcome, sync_once

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 300
MAX_BACKOFF_SECONDS = 3600
BACKOFF_FACTOR = 2
JOIN_TIMEOUT_SECONDS = 5.0
UNEXPECTED_STATUS = "Erreur inattendue de synchronisation (voir le fichier de log)"
Engine = Callable[[sqlite3.Connection, SyncOptions], SyncOutcome]


class SyncWorker:
    """Runs rounds in a daemon thread. `load_options` is called before every round, so the player's settings
    take effect without a restart; after a refused key the worker waits until the player saves another key."""

    def __init__(self, database_path: Callable[[], str], load_options: Callable[[], SyncOptions | None],
                 interval: float = SYNC_INTERVAL_SECONDS, engine: Engine = sync_once) -> None:
        self._database_path, self._load_options = database_path, load_options
        self._interval, self._engine = interval, engine
        self._delay = interval
        self._stop = threading.Event()
        self._status = ""
        self._refused_key: str | None = None
        self._thread = threading.Thread(target=self._run, name="sync-worker", daemon=True)

    def start(self) -> None:
        """Start the thread (the first round runs at once)."""
        self._thread.start()

    def stop(self) -> None:
        """Ask the thread to end and wait for it briefly."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(JOIN_TIMEOUT_SECONDS)

    def is_running(self) -> bool:
        """True while the thread is alive."""
        return self._thread.is_alive()

    def status(self) -> str:
        """The message of the last round, for the settings card (empty before any round)."""
        return self._status

    def next_delay(self, outcome: SyncOutcome) -> float:
        """Seconds to wait before the next round: the interval after a success, doubled (up to the cap) after a failure."""
        if outcome.message == DONE_MESSAGE:
            self._delay = self._interval
        else:
            self._delay = min(max(self._delay * BACKOFF_FACTOR, self._interval), MAX_BACKOFF_SECONDS)
        return self._delay

    def _run(self) -> None:
        delay = 0.0
        while not self._stop.wait(delay):
            delay = self._round()

    def _round(self) -> float:
        options = self._load_options()
        if options is None:
            self._status, self._delay = "", self._interval
            return self._interval
        if options.key == self._refused_key:  # the server refused this key: wait for the player to save another
            return self._interval
        self._refused_key = None
        try:
            outcome = self._run_engine(options)
        except Exception:  # a worker thread reports and survives; the cause goes to the log
            logger.exception("synchronisation échouée")
            outcome = SyncOutcome(0, 0, False, UNEXPECTED_STATUS)
        self._status = outcome.message
        if outcome.refused:
            self._refused_key, self._delay = options.key, self._interval
            return self._interval
        return self.next_delay(outcome)

    def _run_engine(self, options: SyncOptions) -> SyncOutcome:
        store = PriceStore(self._database_path())
        try:
            return self._engine(store.connection, options)
        finally:
            store.close()
