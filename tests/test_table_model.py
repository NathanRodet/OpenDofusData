"""Tests of the table rows, sorting and limit."""

from opendofusdata.table_model import TABLE_ROW_LIMIT, TableRow, limit_rows, sort_rows


def rows_of(values: list[object]) -> list[TableRow]:
    return [TableRow(index, (str(value),), (value,)) for index, value in enumerate(values)]


def test_ascending_puts_unknown_last() -> None:
    assert [row.sort_values[0] for row in sort_rows(rows_of([3, None, 1]), 0, False)] == [1, 3, None]


def test_descending_still_puts_unknown_last() -> None:
    assert [row.sort_values[0] for row in sort_rows(rows_of([3, None, 1]), 0, True)] == [3, 1, None]


def test_equal_values_keep_their_order() -> None:
    rows = [TableRow(key, ("x",), (1,)) for key in "abc"]
    assert [row.key for row in sort_rows(rows, 0, True)] == ["a", "b", "c"]


def test_limit_rows_reports_truncation() -> None:
    kept, truncated = limit_rows(rows_of(list(range(TABLE_ROW_LIMIT + 1))))
    assert (len(kept), truncated) == (TABLE_ROW_LIMIT, True)
    kept, truncated = limit_rows(rows_of(list(range(TABLE_ROW_LIMIT))))
    assert (len(kept), truncated) == (TABLE_ROW_LIMIT, False)
