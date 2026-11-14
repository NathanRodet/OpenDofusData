"""Regression tests for the bugs found by the whole-branch review of the V2."""

import logging
import time
from datetime import datetime, timezone

import pytest

from opendofusdata.reset_data import collected_counts
from opendofusdata.time_filters import PERIOD_TODAY, PeriodSelection, parse_custom_range, period_window
from opendofusdata.view_connection import open_view_connection

UTC = timezone.utc
PARIS_SYSTEM = time.timezone == -3600 and time.daylight == 1
needs_paris = pytest.mark.skipif(not PARIS_SYSTEM, reason="needs the Europe/Paris system time zone")


@needs_paris
def test_today_uses_the_system_offset_of_the_day_itself() -> None:
    selection = PeriodSelection(PERIOD_TODAY)
    autumn = period_window(selection, datetime(2026, 10, 25, 12, 0, tzinfo=UTC))[0]
    spring = period_window(selection, datetime(2026, 3, 29, 12, 0, tzinfo=UTC))[0]
    assert autumn == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    assert spring == datetime(2026, 3, 28, 23, 0, tzinfo=UTC)


@needs_paris
def test_custom_range_follows_the_offset_of_each_day() -> None:
    start, end = parse_custom_range("24/10/2026", "25/10/2026")
    assert start == datetime(2026, 10, 23, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)


def test_a_year_out_of_range_is_an_invalid_date_not_a_crash() -> None:
    for text in ("01/01/1960", "12/11/0026"):
        with pytest.raises(ValueError):
            parse_custom_range(text, "12/11/2026")


def test_reset_counts_do_not_create_a_missing_database(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        collected_counts(str(tmp_path / "nope.db"))
    assert list(tmp_path.iterdir()) == []


def test_a_missing_database_is_reported_once(tmp_path, caplog) -> None:
    path = str(tmp_path / "absent-once.db")
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert open_view_connection(path) is None
    assert caplog.text.count("absent-once.db") == 1


def test_table_does_not_scroll_back_and_selects_one_row_for_duplicate_keys(root) -> None:
    from opendofusdata.table_model import TableRow
    from opendofusdata.ui_table import Column, DataTable

    table = DataTable(root, [Column("A", 80)], lambda key: None, (0, False))
    table.pack(fill="both", expand=True)
    rows = [TableRow("same", (f"{index:04d}",), (f"{index:04d}",)) for index in range(300)]
    table.set_rows(rows)
    table._tree.selection_set("3")
    root.update()
    table._tree.yview_moveto(0.5)
    root.update()
    before = table._tree.yview()[0]
    table.set_rows(rows)
    root.update()
    assert table._tree.selection() == ("0",) and table._tree.yview()[0] == pytest.approx(before, abs=0.01)


def test_unchanged_chart_is_not_redrawn(root) -> None:
    import customtkinter

    from opendofusdata.ui_chart import ChartPoint, DatedChart

    chart = DatedChart(customtkinter.CTkFrame(root))
    chart.pack()
    points = [ChartPoint(datetime(2026, 11, 12, hour, tzinfo=UTC), 500 + hour, "") for hour in (1, 2)]
    chart.set_series(points, "kamas")
    first = set(chart._plot.find_all())
    chart.set_series(list(points), "kamas")
    assert set(chart._plot.find_all()) == first
