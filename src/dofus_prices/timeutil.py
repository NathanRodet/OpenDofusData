"""Timestamp parsing and formatting helpers: pure logic."""

import re
from datetime import datetime, timezone

STORED_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MICROSECOND_DIGITS = 6
SERVER_TIMESTAMP_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z")


def format_utc(moment: datetime) -> str:
    """Format an aware datetime as UTC text; a naive datetime raises ValueError."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("naive datetime has no defined UTC time")
    return moment.astimezone(timezone.utc).strftime(STORED_TIMESTAMP_FORMAT)


def parse_server_timestamp(text: str) -> datetime:
    """Parse a server UTC timestamp (up to 9 fractional digits) into an aware datetime."""
    match = SERVER_TIMESTAMP_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid server timestamp: {text!r}")
    base, fraction = match.groups()
    microseconds = int((fraction or "").ljust(MICROSECOND_DIGITS, "0")[:MICROSECOND_DIGITS])
    moment = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
    return moment.replace(microsecond=microseconds, tzinfo=timezone.utc)
