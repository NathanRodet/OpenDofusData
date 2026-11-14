"""Rows of a data table, sorting and size limit: pure logic."""

from collections.abc import Sequence
from dataclasses import dataclass

TABLE_ROW_LIMIT = 5_000


@dataclass(frozen=True)
class TableRow:
    """One table line: its identity, the shown texts, the values to sort by and an optional colour tag."""

    key: object
    cells: tuple[str, ...]
    sort_values: tuple[object, ...]
    tag: str | None = None
    children: tuple["TableRow", ...] = ()  # rows shown when this one is unfolded
    group: object | None = None  # stable identity of a group, to keep it unfolded across refreshes


def sort_rows(rows: Sequence[TableRow], column: int, descending: bool) -> list[TableRow]:
    """Sort by one column; unknown values (None) always come last, equal values keep their order."""
    known = [row for row in rows if row.sort_values[column] is not None]
    unknown = [row for row in rows if row.sort_values[column] is None]
    known.sort(key=lambda row: row.sort_values[column], reverse=descending)
    return known + unknown


def limit_rows(rows: Sequence[TableRow], limit: int = TABLE_ROW_LIMIT) -> tuple[list[TableRow], bool]:
    """The first `limit` rows and whether some were left out."""
    return list(rows[:limit]), len(rows) > limit
