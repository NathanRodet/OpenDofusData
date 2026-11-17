"""Headless-safe checks of the table, the period bar and the split layout."""

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.table_model import TABLE_ROW_LIMIT, TableRow
from opendofusdata.time_filters import PERIOD_ALL, PERIOD_CUSTOM, PERIOD_LAST_HOUR
from opendofusdata.ui_period import BAD_DATE_MESSAGE, PeriodBar
from opendofusdata.ui_split import LAYOUT_BELOW, LAYOUT_RIGHT, SplitLayout
from opendofusdata.ui_table import Column, DataTable

COLUMNS = [Column("Objet", 120), Column("Prix", 80, numeric=True)]


def row(key: str, price: int | None) -> TableRow:
    return TableRow(key, (key, "Inconnu" if price is None else str(price)), (key, price))


def make_table(root, selected: list) -> DataTable:
    table = DataTable(root, COLUMNS, selected.append, (1, False))
    table.pack()
    return table


def test_table_sorts_on_header_click_and_keeps_unknown_last(root) -> None:
    table = make_table(root, [])
    table.set_rows([row("b", 20), row("x", None), row("a", 10), row("c", 30)])
    assert [r.key for r in table._shown] == ["a", "b", "c", "x"]
    table._header_clicked(1)
    assert [r.key for r in table._shown] == ["c", "b", "a", "x"]


def test_table_keeps_the_selected_row_when_rows_are_replaced(root) -> None:
    selected: list = []
    table = make_table(root, selected)
    table.set_rows([row("a", 10), row("b", 20)])
    table._tree.selection_set("1")
    root.update_idletasks()
    table.set_rows([row("c", 5), row("a", 10), row("b", 21)])
    assert table.selected_key() == "b"
    table.set_rows([row("c", 5)])
    assert table.selected_key() is None and selected[-1] is None


def test_table_reports_truncation_above_the_limit(root) -> None:
    table = make_table(root, [])
    assert table.set_rows([row(str(index), index) for index in range(TABLE_ROW_LIMIT + 1)]) is True
    assert table.set_rows([row("a", 1)]) is False


def test_period_bar_defaults_to_all_and_reports_changes(root) -> None:
    changes: list[int] = []
    bar = PeriodBar(root, lambda: changes.append(1))
    assert bar.selection().period == PERIOD_ALL
    bar.set_period(PERIOD_LAST_HOUR)
    assert bar.selection().period == PERIOD_LAST_HOUR and changes == [1]


def test_custom_period_rejects_a_bad_date_and_accepts_a_good_one(root) -> None:
    changes: list[int] = []
    bar = PeriodBar(root, lambda: changes.append(1))
    bar.set_period(PERIOD_CUSTOM)
    bar.start_entry.insert(0, "31/02/2026")
    bar.end_entry.insert(0, "01/03/2026")
    bar.apply_custom()
    assert bar.message_label.cget("text") == BAD_DATE_MESSAGE
    assert bar.selection().period == PERIOD_ALL and changes == []
    bar.start_entry.delete(0, "end")
    bar.start_entry.insert(0, "10/11/2026")
    bar.end_entry.delete(0, "end")
    bar.end_entry.insert(0, "12/11/2026")
    bar.apply_custom()
    assert bar.selection().period == PERIOD_CUSTOM and changes == [1]


def test_split_layout_moves_the_detail_below_when_narrow(root) -> None:
    split = SplitLayout(root)
    split.relayout(900)
    assert split.layout_mode == LAYOUT_BELOW
    assert int(split.detail.grid_info()["row"]) == 1
    split.relayout(1300)
    assert split.layout_mode == LAYOUT_RIGHT
    assert int(split.detail.grid_info()["column"]) == 1


def test_rows_alternate_their_background(root) -> None:
    table = make_table(root, [])
    table.set_rows([row("a", 1), row("b", 2), row("c", 3)])
    tags = [table._tree.item(str(index), "tags") for index in range(3)]
    assert ["stripe" in item for item in tags] == [False, True, False]


class Resized:
    """The part of a Configure event the table reads."""

    def __init__(self, width: int) -> None:
        self.width = width


def column_widths(table: DataTable) -> list[int]:
    return [int(table._tree.column(name, "width")) for name in table._tree["columns"]]


def test_columns_shrink_together_when_the_table_is_narrower_than_their_widths(root) -> None:
    table = DataTable(root, [Column("A", 300), Column("B", 300), Column("C", 300)], lambda key: None, (0, False))
    table._fit_columns(Resized(450))
    assert column_widths(table) == [150, 150, 150]


def test_columns_never_shrink_below_half_their_width(root) -> None:
    table = DataTable(root, [Column("A", 300), Column("B", 300)], lambda key: None, (0, False))
    table._fit_columns(Resized(100))
    assert column_widths(table) == [150, 150]


def test_columns_return_to_their_widths_when_the_table_is_wide_enough(root) -> None:
    table = DataTable(root, [Column("A", 300), Column("B", 300)], lambda key: None, (0, False))
    table._fit_columns(Resized(300))
    table._fit_columns(Resized(900))
    assert column_widths(table) == [300, 300]


def test_an_unlaid_table_keeps_its_starting_widths(root) -> None:
    table = DataTable(root, [Column("A", 300)], lambda key: None, (0, False))
    table._fit_columns(Resized(1))
    assert column_widths(table) == [300]
