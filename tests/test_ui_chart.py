"""Headless-safe checks of the dated chart."""

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("customtkinter")

from opendofusdata.ui_chart import EMPTY_TEXT, ChartPoint, DatedChart, tooltip_text

UTC = timezone.utc
ZONE = timezone(timedelta(hours=1))
START = datetime(2026, 11, 12, 17, 42, tzinfo=UTC)


def points(count: int) -> list[ChartPoint]:
    return [ChartPoint(START + timedelta(hours=index), 500 + index * 50, f"{40 + index} objets vendus")
            for index in range(count)]


def count_items(chart: DatedChart, tag: str) -> int:
    return len(chart._plot.find_withtag(tag))


def test_chart_draws_one_dot_per_point(root) -> None:
    chart = DatedChart(root)
    chart.pack()
    chart.set_series(points(3), "kamas")
    assert count_items(chart, "dot") == 3
    assert count_items(chart, "line") == 1


def test_chart_without_points_shows_the_empty_text(root) -> None:
    chart = DatedChart(root)
    chart.pack()
    chart.set_series([], "kamas")
    (item,) = chart._plot.find_withtag("empty")
    assert chart._plot.itemcget(item, "text") == EMPTY_TEXT
    assert count_items(chart, "dot") == 0


def test_tooltip_text_names_date_value_and_detail() -> None:
    point = ChartPoint(START, 557, "46 objets vendus")
    assert tooltip_text(point, "kamas", 0, ZONE).split("\n") == ["12/11 18:42", "557 kamas", "46 objets vendus"]


def test_nearest_point_follows_the_pointer(root) -> None:
    chart = DatedChart(root)
    chart.pack()
    chart.set_series(points(3), "kamas")
    first_x, last_x = chart._positions[0][0], chart._positions[-1][0]
    assert chart.nearest_index(first_x - 5) == 0
    assert chart.nearest_index(last_x + 5) == 2


def test_single_point_does_not_crash(root) -> None:
    chart = DatedChart(root)
    chart.pack()
    chart.set_series(points(1), "kamas")
    assert count_items(chart, "dot") == 1
    chart.clear()
    assert count_items(chart, "dot") == 0
