"""Axis ticks and linear scaling for the charts: pure logic."""

from datetime import datetime, timedelta, tzinfo

DEFAULT_TICK_COUNT = 5
FLAT_RANGE_WIDENING = 1.0
HOUR_TICK_STEP = 4
DAY_MODE_FROM = timedelta(days=2)
MIDNIGHT_FORMAT = "%d/%m"
HOUR_FORMAT = "%H:00"


def value_ticks(low: float, high: float, count: int = DEFAULT_TICK_COUNT) -> list[float]:
    """`count` equally spaced values from low to high; a flat range is widened by one."""
    if high <= low:
        high = low + FLAT_RANGE_WIDENING
    step = (high - low) / (count - 1)
    return [low + step * index for index in range(count)]


def scale(value: float, low: float, high: float, pixels: float) -> float:
    """Linear position of a value between low and high over `pixels`; a flat range gives 0."""
    if high == low:
        return 0.0
    return (value - low) / (high - low) * pixels


def _first_hour_tick(start: datetime) -> datetime:
    tick = start.replace(minute=0, second=0, microsecond=0)
    while tick < start or tick.hour % HOUR_TICK_STEP != 0:
        tick += timedelta(hours=1)
    return tick


def _first_midnight(start: datetime) -> datetime:
    tick = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return tick if tick >= start else tick + timedelta(days=1)


def _label(tick: datetime) -> str:
    return tick.strftime(MIDNIGHT_FORMAT) if tick.hour == 0 else tick.strftime(HOUR_FORMAT)


def time_ticks(start: datetime, end: datetime, local_zone: tzinfo | None = None) -> list[tuple[datetime, str]]:
    """Date ticks: every 4 h (the date at midnight), or every midnight when the span exceeds 2 days."""
    local_start, local_end = start.astimezone(local_zone), end.astimezone(local_zone)
    daily = local_end - local_start > DAY_MODE_FROM
    tick = _first_midnight(local_start) if daily else _first_hour_tick(local_start)
    step = timedelta(days=1) if daily else timedelta(hours=HOUR_TICK_STEP)
    ticks = []
    while tick <= local_end:
        ticks.append((tick, _label(tick)))
        tick += step
    return ticks
