"""Data categories the player can enable or disable, and the writer that filters on them."""

import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from opendofusdata.records import Record, RecyclingEvent
from opendofusdata.session_counters import RecordSink

CATEGORY_HDV = "hdv"
CATEGORY_RECYCLING = "recycling"
CATEGORY_BREAKING = "breaking"
CATEGORY_PETS = "pets"
ENABLED_KEY = "enabled_categories"


@dataclass(frozen=True)
class DataCategory:
    """One kind of collected data; `available` is False until its decoder exists."""

    key: str
    label: str
    available: bool


CATEGORIES = (
    DataCategory(CATEGORY_HDV, "HDV", True),
    DataCategory(CATEGORY_RECYCLING, "Recyclage des ressources (bêta)", True),
    DataCategory(CATEGORY_BREAKING, "Brisage", False),
    DataCategory(CATEGORY_PETS, "Expérience des pets", False),
)
KNOWN_KEYS = tuple(category.key for category in CATEGORIES)
CATEGORY_LABELS = {category.key: category.label for category in CATEGORIES}
DEFAULT_ENABLED = (CATEGORY_HDV,)


class CategorySettings:
    """The enabled categories, safe to read from the capture thread and write from the window."""

    def __init__(self, enabled: Iterable[str]) -> None:
        self._lock = threading.Lock()
        self._enabled = {key for key in enabled if key in KNOWN_KEYS}

    def is_enabled(self, key: str) -> bool:
        """True when the category is enabled."""
        with self._lock:
            return key in self._enabled

    def set_enabled(self, key: str, enabled: bool) -> None:
        """Enable or disable a known category (unknown keys are ignored)."""
        if key not in KNOWN_KEYS:
            return
        with self._lock:
            (self._enabled.add if enabled else self._enabled.discard)(key)

    def enabled_keys(self) -> list[str]:
        """Enabled keys in the order of CATEGORIES."""
        with self._lock:
            return [key for key in KNOWN_KEYS if key in self._enabled]


def categories_from_config(config: Mapping[str, object]) -> CategorySettings:
    """Read the enabled categories; a missing or invalid value gives the default (HDV only)."""
    saved = config.get(ENABLED_KEY)
    if isinstance(saved, list) and all(isinstance(item, str) for item in saved):
        return CategorySettings(saved)
    return CategorySettings(DEFAULT_ENABLED)


def config_with_categories(config: Mapping[str, object], settings: CategorySettings) -> dict[str, object]:
    """Return a copy of the config holding the current enabled categories."""
    return {**config, ENABLED_KEY: settings.enabled_keys()}


def category_of(record: Record) -> str:
    """The data category a record belongs to."""
    return CATEGORY_RECYCLING if isinstance(record, RecyclingEvent) else CATEGORY_HDV


class FilteringWriter:
    """Forwards records to a sink only while their category is enabled."""

    def __init__(self, sink: RecordSink, settings: CategorySettings) -> None:
        self._sink = sink
        self._settings = settings

    def submit(self, record: Record) -> None:
        """Forward the record when its category is enabled; drop it otherwise."""
        if self._settings.is_enabled(category_of(record)):
            self._sink.submit(record)
