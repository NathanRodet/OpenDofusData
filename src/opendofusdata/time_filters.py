"""Period windows and elapsed-time text for the views: pure logic."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone, tzinfo

from opendofusdata.timeutil import format_utc, parse_server_timestamp

PERIOD_LAST_HOUR = "Dernière heure"
PERIOD_SIX_HOURS = "6 heures"
PERIOD_TODAY = "Aujourd'hui"
PERIOD_WEEK = "7 jours"
PERIOD_MONTH = "30 jours"
PERIOD_ALL = "Tout"
PERIOD_CUSTOM = "Personnalisé"
PERIODS = (PERIOD_LAST_HOUR, PERIOD_SIX_HOURS, PERIOD_TODAY, PERIOD_WEEK, PERIOD_MONTH, PERIOD_ALL, PERIOD_CUSTOM)

RELATIVE_PERIODS = {
    PERIOD_LAST_HOUR: timedelta(hours=1),
    PERIOD_SIX_HOURS: timedelta(hours=6),
    PERIOD_WEEK: timedelta(days=7),
    PERIOD_MONTH: timedelta(days=30),
}
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
LOCAL_FORMAT = "%d/%m %H:%M"
Window = tuple[datetime | None, datetime | None]


@dataclass(frozen=True)
class PeriodSelection:
    """The period chosen in a view; custom bounds only matter for PERIOD_CUSTOM."""

    period: str = PERIOD_TODAY
    custom_start: datetime | None = None
    custom_end: datetime | None = None


def _local_midnight(now: datetime, local_zone: tzinfo | None) -> datetime:
    local_now = now.astimezone(local_zone)
    midnight = datetime.combine(local_now.date(), time.min, tzinfo=local_now.tzinfo)
    return midnight.astimezone(timezone.utc)


def period_window(selection: PeriodSelection, now: datetime, local_zone: tzinfo | None = None) -> Window:
    """The (start, end) bounds in UTC of a selection; None means unbounded."""
    if selection.period == PERIOD_TODAY:
        return _local_midnight(now, local_zone), None
    if selection.period == PERIOD_CUSTOM:
        return selection.custom_start, selection.custom_end
    if selection.period in RELATIVE_PERIODS:
        return now - RELATIVE_PERIODS[selection.period], None
    return None, None


def elapsed_text(moment: datetime, now: datetime) -> str:
    """Elapsed time in minutes under an hour, hours under a day, days after."""
    minutes = max(1, int((now - moment).total_seconds()) // SECONDS_PER_MINUTE)
    if minutes < MINUTES_PER_HOUR:
        return f"il y a {minutes} min"
    hours = minutes // MINUTES_PER_HOUR
    if hours < HOURS_PER_DAY:
        return f"il y a {hours} h"
    return f"il y a {hours // HOURS_PER_DAY} j"


def local_text(moment: datetime, local_zone: tzinfo | None = None) -> str:
    """The exact local date and time, like 12/11 18:42."""
    return moment.astimezone(local_zone).strftime(LOCAL_FORMAT)


def parse_stored(text: str) -> datetime:
    """Parse a stored UTC timestamp into an aware datetime."""
    return parse_server_timestamp(text)


STORED_MINIMUM = ""
STORED_MAXIMUM = "9999-12-31T23:59:59Z"


def stored_bounds(window: Window) -> tuple[str, str]:
    """The window as stored-timestamp text bounds, usable in a SQL BETWEEN."""
    start, end = window
    return (format_utc(start) if start else STORED_MINIMUM, format_utc(end) if end else STORED_MAXIMUM)
