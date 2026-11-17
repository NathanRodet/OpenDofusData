"""The progress of the reference data download, shared between the worker thread and the window."""

import re
import threading

PAGES_PATTERN = re.compile(r"^\s*(?P<label>\S+)\s*:\s*(?P<done>\d+)/(?P<total>\d+) pages")


class DownloadProgress:
    """Remembers the last 'label : done/total pages' message reported by the download."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._label, self._done, self._total = "", 0, 0

    def report(self, message: str) -> None:
        """Keep the message when it carries a page count (other messages are ignored)."""
        match = PAGES_PATTERN.match(message)
        if match is None:
            return
        with self._lock:
            self._label, self._done, self._total = match["label"], int(match["done"]), int(match["total"])

    def reset(self) -> None:
        """Forget the previous download."""
        with self._lock:
            self._label, self._done, self._total = "", 0, 0

    def pages(self) -> str:
        """'12/45' while a download reported something, else an empty text."""
        with self._lock:
            return f"{self._done}/{self._total}" if self._total else ""

    def detail(self) -> str:
        """'items 12/45 pages' while a download reported something, else an empty text."""
        with self._lock:
            return f"{self._label} {self._done}/{self._total} pages" if self._total else ""
