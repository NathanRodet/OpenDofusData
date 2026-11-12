"""Filters of the Logs page: kind, text and period (pure logic)."""

from collections.abc import Sequence

from opendofusdata.log_feed import LogEntry, NameLookup, format_log_row
from opendofusdata.time_filters import Window

KIND_ALL = "Tout"
KINDS = (KIND_ALL, "HDV", "Brisage", "Familier")
NAME_CELL = 2


def filter_entries(entries: Sequence[LogEntry], text: str, kind: str, window: Window,
                   name_of: NameLookup) -> list[LogEntry]:
    """Entries of the chosen kind whose shown name contains the text and that fall inside the window."""
    start, end = window
    wanted = text.strip().casefold()
    return [entry for entry in entries
            if (kind == KIND_ALL or entry.category == kind)
            and (start is None or entry.moment >= start) and (end is None or entry.moment < end)
            and wanted in format_log_row(entry, name_of)[NAME_CELL].casefold()]
