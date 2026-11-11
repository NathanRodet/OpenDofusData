"""Run one job in a worker thread and expose its state to the window (no GUI dependency)."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

UNEXPECTED_MESSAGE = "erreur inattendue (voir le fichier de log)"


class TaskState(Enum):
    """Lifecycle of a background task."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class TaskSnapshot:
    """The task state and its result text (or its error text when failed)."""

    state: TaskState
    message: str


class BackgroundTask:
    """Runs `work` in a thread; `work` returns a result text, `failures` are expected errors."""

    def __init__(self, work: Callable[[], str], failures: tuple[type[Exception], ...]) -> None:
        self._work, self._failures = work, failures
        self._lock = threading.Lock()
        self._snapshot = TaskSnapshot(TaskState.IDLE, "")
        self._finished = threading.Event()
        self._finished.set()

    def snapshot(self) -> TaskSnapshot:
        """The current state and message."""
        with self._lock:
            return self._snapshot

    def start(self) -> bool:
        """Start the job; returns False (and does nothing) while it is already running."""
        with self._lock:
            if self._snapshot.state is TaskState.RUNNING:
                return False
            self._snapshot = TaskSnapshot(TaskState.RUNNING, "")
            self._finished.clear()
        threading.Thread(target=self._run, name="background-task", daemon=True).start()
        return True

    def wait(self, timeout: float) -> bool:
        """Wait for the running job to end; True when it has ended."""
        return self._finished.wait(timeout)

    def _run(self) -> None:
        try:
            snapshot = TaskSnapshot(TaskState.DONE, self._work())
        except self._failures as error:
            snapshot = TaskSnapshot(TaskState.FAILED, str(error))
        except Exception:  # a worker thread must report, never die silently
            logger.exception("background task failed")
            snapshot = TaskSnapshot(TaskState.FAILED, UNEXPECTED_MESSAGE)
        with self._lock:
            self._snapshot = snapshot
        self._finished.set()
