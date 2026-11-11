"""Bounded feed of the captured records, shown in the Logs page (pure logic, no GUI)."""

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from opendofusdata.categories import CATEGORY_HDV, CATEGORY_LABELS
from opendofusdata.records import MARKET_PERIODS, LotPrice, MarketStats
from opendofusdata.session_counters import RecordSink

MAX_LOG_LINES = 200
TIME_FORMAT = "%H:%M:%S"
NameLookup = Callable[[int], str]
LOG_COLUMNS = ("Heure", "Type", "Objet", "Détail", "Valeur")
HDV_LABEL = CATEGORY_LABELS[CATEGORY_HDV]
PERIOD_UNITS = {"h": "h", "d": "j"}  # hours stay h, days become j (jours)
PERIOD_LABELS = {period: f"stats {period[:-1]} {PERIOD_UNITS[period[-1]]}" for period in MARKET_PERIODS}
LOT_DETAIL = "lot ×{size}"


LOG_COLUMN_WIDTHS = (8, 4, 26, 10, 8)
COLUMN_SEPARATOR = "  "
ELLIPSIS = "…"


def shorten(text: str, width: int) -> str:
    """Cut a text to `width` characters, ending with an ellipsis when it was longer."""
    return text if len(text) <= width else text[: width - 1] + ELLIPSIS


def format_log_line(cells: tuple[str, ...]) -> str:
    """One monospace line: fixed-width columns, the last (value) right-aligned."""
    last = len(cells) - 1
    parts = [shorten(cell, width).rjust(width) if index == last else shorten(cell, width).ljust(width)
             for index, (cell, width) in enumerate(zip(cells, LOG_COLUMN_WIDTHS))]
    return COLUMN_SEPARATOR.join(parts)


@dataclass(frozen=True)
class LogEntry:
    """One captured record, reduced to what the Logs page shows."""

    moment: datetime
    category: str
    item_id: int
    detail: str
    value: str


def format_number(value: int) -> str:
    """Group thousands with a space (82985 -> '82 985')."""
    return f"{value:,}".replace(",", " ")


def entry_from_record(record: LotPrice | MarketStats, moment: datetime) -> LogEntry:
    """Summarise a lot price (price of the lot) or market stats (median)."""
    if isinstance(record, LotPrice):
        return LogEntry(moment, HDV_LABEL, record.item_id,
                        LOT_DETAIL.format(size=record.lot_size), format_number(record.price))
    detail = PERIOD_LABELS.get(record.period, record.period)
    return LogEntry(moment, HDV_LABEL, record.item_id, detail, format_number(record.median))


def format_log_row(entry: LogEntry, name_of: NameLookup) -> tuple[str, str, str, str, str]:
    """The five displayed cells: time (local), type, item name, detail, value."""
    shown_time = entry.moment.astimezone().strftime(TIME_FORMAT)
    return shown_time, entry.category, name_of(entry.item_id), entry.detail, entry.value


class LogFeed:
    """The last records captured; accumulates only while visible, newest first."""

    def __init__(self, capacity: int = MAX_LOG_LINES) -> None:
        self._lock = threading.Lock()
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._visible = False

    def set_visible(self, visible: bool) -> None:
        """Show or hide the feed; changing the state empties it."""
        with self._lock:
            if visible != self._visible:
                self._entries.clear()
            self._visible = visible

    def is_visible(self) -> bool:
        """True while the player wants the logs displayed."""
        with self._lock:
            return self._visible

    def add(self, record: LotPrice | MarketStats, moment: datetime) -> None:
        """Remember a record when the feed is visible; ignore it otherwise."""
        with self._lock:
            if self._visible:
                self._entries.appendleft(entry_from_record(record, moment))

    def entries(self) -> list[LogEntry]:
        """The remembered entries, newest first."""
        with self._lock:
            return list(self._entries)


class FeedWriter:
    """Forwards records to a sink, then adds them to the log feed."""

    def __init__(self, sink: RecordSink, feed: LogFeed, now: Callable[[], datetime]) -> None:
        self._sink = sink
        self._feed = feed
        self._now = now

    def submit(self, record: LotPrice | MarketStats) -> None:
        """Queue the record in the sink, then feed the log."""
        self._sink.submit(record)
        self._feed.add(record, self._now())
