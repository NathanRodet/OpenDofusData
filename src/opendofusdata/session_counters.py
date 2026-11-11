"""Thread-safe counters of the records saved during a capture session."""

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from opendofusdata.records import LotPrice, PetFeeding, Record, RecyclingEvent


class RecordSink(Protocol):
    """Anything that accepts decoded records (the StoreWriter)."""

    def submit(self, record: Record) -> None: ...


class SessionCounters:
    """Counts price and stats records and remembers when the last one arrived."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._price_count = 0
        self._stats_count = 0
        self._recycling_count = 0
        self._pet_count = 0
        self._last_record_at: datetime | None = None

    def record(self, record: Record, moment: datetime) -> None:
        """Count one record received at the given moment."""
        with self._lock:
            if isinstance(record, LotPrice):
                self._price_count += 1
            elif isinstance(record, RecyclingEvent):
                self._recycling_count += 1
            elif isinstance(record, PetFeeding):
                self._pet_count += 1
            else:
                self._stats_count += 1
            self._last_record_at = moment

    def recycling_count(self) -> int:
        """Number of recyclings recorded in this session."""
        with self._lock:
            return self._recycling_count

    def pet_count(self) -> int:
        """Number of pet upgrades recorded in this session."""
        with self._lock:
            return self._pet_count

    def read(self) -> tuple[int, int, datetime | None]:
        """Return (price records, stats records, time of the last record)."""
        with self._lock:
            return self._price_count, self._stats_count, self._last_record_at


class CountingWriter:
    """Forwards records to a sink and counts them."""

    def __init__(self, sink: RecordSink, counters: SessionCounters, now: Callable[[], datetime]) -> None:
        self._sink = sink
        self._counters = counters
        self._now = now

    def submit(self, record: Record) -> None:
        """Queue the record in the sink, then count it."""
        self._sink.submit(record)
        self._counters.record(record, self._now())
