"""A dated line chart: price axis on the left, dates below, a tooltip on the nearest point."""

import tkinter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, tzinfo

import customtkinter

from opendofusdata.chart_geometry import scale, time_ticks, value_ticks
from opendofusdata.time_filters import local_text
from opendofusdata.ui_theme import ACCENT_COLOR, LOG_COLOR, MUTED_COLOR, SELECTED_COLOR, TEXT_COLOR, TRANSPARENT

EMPTY_TEXT = "Pas encore de données"
FALLBACK_WIDTH = 400
LEFT_MARGIN = 64
RIGHT_MARGIN = 16
TOP_MARGIN = 14
BOTTOM_MARGIN = 28
DOT_RADIUS = 3
TOOLTIP_PADDING = 8
FILL_COLOR = "#1f3a52"
GRID_COLOR = "#3a3a3a"
AXIS_FONT = ("Segoe UI", 9)


@dataclass(frozen=True)
class ChartPoint:
    """One point: when, how much, and a short text for the tooltip."""

    moment: datetime
    value: float
    detail: str


def format_value(value: float, decimals: int) -> str:
    """A value with spaces between the thousands and the wanted decimals (comma)."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def tooltip_text(point: ChartPoint, unit: str, decimals: int, local_zone: tzinfo | None = None) -> str:
    """Local date, value with unit and detail, one per line."""
    lines = [local_text(point.moment, local_zone), f"{format_value(point.value, decimals)} {unit}"]
    return "\n".join(lines + ([point.detail] if point.detail else []))


class DatedChart(customtkinter.CTkFrame):
    """Draws a series of points on a canvas and redraws itself when resized."""

    def __init__(self, parent: tkinter.Misc, height: int = 210, local_zone: tzinfo | None = None) -> None:
        super().__init__(parent, fg_color=TRANSPARENT, corner_radius=0)
        self._plot = tkinter.Canvas(self, height=height, bg=LOG_COLOR, highlightthickness=0)
        self._plot.pack(fill="both", expand=True)
        self._points: list[ChartPoint] = []
        self._positions: list[tuple[float, float]] = []
        self._unit, self._decimals, self._zone = "", 0, local_zone
        self._plot.bind("<Configure>", lambda _event: self._redraw())
        self._plot.bind("<Motion>", self._pointer_moved)
        self._plot.bind("<Leave>", lambda _event: self._plot.delete("tooltip"))

    def set_series(self, points: Sequence[ChartPoint], unit: str, decimals: int = 0) -> None:
        """Show the points (sorted by date) with the unit written after each value."""
        self._points = sorted(points, key=lambda point: point.moment)
        self._unit, self._decimals = unit, decimals
        self._redraw()

    def clear(self) -> None:
        """Remove every point."""
        self.set_series([], self._unit, self._decimals)

    def _size(self) -> tuple[int, int]:
        width = int(self._plot.winfo_width())
        return (width if width > 1 else FALLBACK_WIDTH), int(self._plot.winfo_height())

    def _redraw(self) -> None:
        self._plot.delete("all")
        self._positions = []
        width, height = self._size()
        if not self._points:
            self._plot.create_text(width / 2, height / 2, text=EMPTY_TEXT, fill=MUTED_COLOR, tags="empty")
            return
        self._draw_axes(width, height)
        self._draw_line(width, height)

    def _value_range(self) -> tuple[float, float]:
        values = [point.value for point in self._points]
        ticks = value_ticks(min(values), max(values))
        return ticks[0], ticks[-1]

    def _draw_axes(self, width: int, height: int) -> None:
        low, high = self._value_range()
        plot_height = height - TOP_MARGIN - BOTTOM_MARGIN
        for tick in value_ticks(low, high):
            y = TOP_MARGIN + plot_height - scale(tick, low, high, plot_height)
            self._plot.create_line(LEFT_MARGIN, y, width - RIGHT_MARGIN, y, fill=GRID_COLOR, tags="axis")
            self._plot.create_text(LEFT_MARGIN - 6, y, text=format_value(tick, self._decimals), anchor="e",
                                     fill=MUTED_COLOR, font=AXIS_FONT, tags="axis")
        first, last = self._points[0].moment, self._points[-1].moment
        for moment, label in time_ticks(first, last, self._zone):
            x = self._x_of(moment, width)
            self._plot.create_text(x, height - BOTTOM_MARGIN / 2, text=label, fill=MUTED_COLOR, font=AXIS_FONT,
                                     tags="axis")

    def _x_of(self, moment: datetime, width: int) -> float:
        first, last = self._points[0].moment, self._points[-1].moment
        plot_width = width - LEFT_MARGIN - RIGHT_MARGIN
        if last == first:
            return LEFT_MARGIN + plot_width / 2
        return LEFT_MARGIN + scale(moment.timestamp(), first.timestamp(), last.timestamp(), plot_width)

    def _draw_line(self, width: int, height: int) -> None:
        low, high = self._value_range()
        plot_height = height - TOP_MARGIN - BOTTOM_MARGIN
        self._positions = [(self._x_of(point.moment, width),
                            TOP_MARGIN + plot_height - scale(point.value, low, high, plot_height))
                           for point in self._points]
        baseline = TOP_MARGIN + plot_height
        if len(self._positions) > 1:
            flat = [coordinate for position in self._positions for coordinate in position]
            self._plot.create_polygon(self._positions[0][0], baseline, *flat, self._positions[-1][0], baseline,
                                        fill=FILL_COLOR, outline="", tags="fill")
            self._plot.create_line(*flat, fill=ACCENT_COLOR, width=2, tags="line")
        for x, y in self._positions:
            self._plot.create_oval(x - DOT_RADIUS, y - DOT_RADIUS, x + DOT_RADIUS, y + DOT_RADIUS,
                                     fill=ACCENT_COLOR, outline="", tags="dot")

    def nearest_index(self, x: float) -> int | None:
        """The index of the point closest to a horizontal pixel position."""
        if not self._positions:
            return None
        return min(range(len(self._positions)), key=lambda index: abs(self._positions[index][0] - x))

    def _pointer_moved(self, event: tkinter.Event) -> None:
        self._plot.delete("tooltip")
        index = self.nearest_index(event.x)
        if index is None:
            return
        x, y = self._positions[index]
        text = tooltip_text(self._points[index], self._unit, self._decimals, self._zone)
        label = self._plot.create_text(x, y - TOOLTIP_PADDING, text=text, fill=TEXT_COLOR, anchor="s",
                                         justify="left", tags="tooltip")
        left, top, right, bottom = self._plot.bbox(label)
        box = self._plot.create_rectangle(left - TOOLTIP_PADDING, top - TOOLTIP_PADDING, right + TOOLTIP_PADDING,
                                            bottom + TOOLTIP_PADDING, fill=SELECTED_COLOR, outline=ACCENT_COLOR,
                                            tags="tooltip")
        self._plot.tag_raise(label, box)
