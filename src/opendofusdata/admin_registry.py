"""The administrator's local registry (admin_keys.json): who got which key. Never stores a key or the secret."""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from opendofusdata.admin_keys import KEY_ID_PATTERN
from opendofusdata.app_config import load_config, save_config

logger = logging.getLogger(__name__)

REGISTRY_FILE_NAME = "admin_keys.json"
KEYS_FIELD = "keys"
MAX_LABEL_LENGTH = 60


class LabelExistsError(Exception):
    """An active key already carries this label."""


class KeyEntry(NamedTuple):
    """One generated key: its identifier, the player's label, and when it was created and revoked."""

    key_id: str
    label: str
    created_at: str
    revoked_at: str | None


def registry_path(env_path: Path) -> Path:
    """The registry sits next to the .env file."""
    return env_path.parent / REGISTRY_FILE_NAME


def clean_label(text: str) -> str | None:
    """The label without surrounding spaces, or None when empty, too long or holding control characters."""
    label = text.strip()
    if not label or len(label) > MAX_LABEL_LENGTH or not label.isprintable():
        return None
    return label


def utc_now() -> datetime:
    """The current UTC time."""
    return datetime.now(timezone.utc)


def _parse_entry(item: object) -> KeyEntry | None:
    """The entry described by a JSON object, or None when it is malformed."""
    if not isinstance(item, dict):
        return None
    key_id, label, created, revoked = (item.get(name) for name in ("key_id", "label", "created_at", "revoked_at"))
    if not all(isinstance(value, str) and value for value in (key_id, label, created)):
        return None
    if not KEY_ID_PATTERN.fullmatch(key_id):  # a hand-edited identifier would break "Copier la clé"
        return None
    return KeyEntry(key_id, label, created, revoked if isinstance(revoked, str) and revoked else None)


class AdminRegistry:
    """Reads and writes the registry file; safe to use from the window and from a background thread."""

    def __init__(self, path: Path, clock: Callable[[], datetime] = utc_now) -> None:
        self._path, self._clock = path, clock
        self._lock = threading.Lock()

    def entries(self) -> list[KeyEntry]:
        """Every well-formed entry in the file, oldest first; a missing or corrupt file gives an empty list."""
        with self._lock:
            return self._read()

    def _read(self) -> list[KeyEntry]:
        stored = load_config(self._path).get(KEYS_FIELD)
        parsed = [_parse_entry(item) for item in stored] if isinstance(stored, list) else []
        return [entry for entry in parsed if entry is not None]

    def _write(self, entries: list[KeyEntry]) -> None:
        save_config(self._path, {KEYS_FIELD: [entry._asdict() for entry in entries]})

    def add(self, label: str, key_id: str) -> KeyEntry:
        """Record a new key; LabelExistsError when an active key has this label (case ignored)."""
        with self._lock:
            entries = self._read()
            if any(entry.revoked_at is None and entry.label.casefold() == label.casefold() for entry in entries):
                raise LabelExistsError(label)
            entry = KeyEntry(key_id, label, self._clock().isoformat(), None)
            self._write([*entries, entry])
            return entry

    def mark_revoked(self, key_id: str) -> None:
        """Mark this key as revoked now; an unknown identifier changes nothing."""
        with self._lock:
            entries = self._read()
            moment = self._clock().isoformat()
            updated = [entry._replace(revoked_at=moment) if entry.key_id == key_id and entry.revoked_at is None
                       else entry for entry in entries]
            if updated != entries:
                self._write(updated)
