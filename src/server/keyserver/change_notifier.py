"""What the stream tells the players: a counter per kind of data, and the one open stream allowed per key."""

import threading

MAX_STREAMS = 200  # every open stream holds a connection: the server as a whole refuses more than this


class ChangeNotifier:
    """Thread-safe change counters (bumped by the routes that store data) and the stream slots."""

    def __init__(self, max_streams: int = MAX_STREAMS) -> None:
        self._lock = threading.Lock()
        self._versions: dict[str, int] = {}
        self._open_keys: set[str] = set()
        self._max_streams = max_streams

    def notify(self, kind: str) -> None:
        """Remember that new data of this kind was stored."""
        with self._lock:
            self._versions[kind] = self._versions.get(kind, 0) + 1

    def snapshot(self) -> dict[str, int]:
        """The counters now; two snapshots that differ mean something was stored in between."""
        with self._lock:
            return dict(self._versions)

    def open_slot(self, key_id: str) -> bool:
        """Take the stream of this key; False when the key already has one open or the server is full."""
        with self._lock:
            if key_id in self._open_keys or len(self._open_keys) >= self._max_streams:
                return False
            self._open_keys.add(key_id)
            return True

    def close_slot(self, key_id: str) -> None:
        """Give the stream of this key back."""
        with self._lock:
            self._open_keys.discard(key_id)


def changed_kinds(before: dict[str, int], after: dict[str, int]) -> list[str]:
    """The kinds whose counter moved between two snapshots, in name order."""
    return sorted(kind for kind, version in after.items() if before.get(kind) != version)
