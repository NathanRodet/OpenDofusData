"""Strict schemas of the readings sent by the clients: types, bounds, characters and dates."""

import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

MAX_BATCH_READINGS = 2000
MAX_SERVER_NAME_LENGTH = 40
MAX_ITEM_ID = 10_000_000
LOT_SIZES = (1, 10, 100, 1000)
MAX_PRICE = 1_000_000_000_000
MAX_QUERY_INTEGER = 999_999_999_999  # twelve digits, the most a query parameter may carry
OBSERVATION_RETENTION_DAYS = 7  # a reading older than the journal keeps is refused: it would be purged at once
FUTURE_TOLERANCE = timedelta(minutes=5)
# A letter or digit (accents included), then letters, digits, spaces, hyphens or underscores.
SERVER_NAME_PATTERN = r"^[^\W_][\w -]{0,39}$"
KEY_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"

STRICT_MODEL = ConfigDict(extra="forbid", strict=True)
# Unicode categories that print nothing: control, format (zero width...), surrogate, private, unassigned, separators.
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def utc_now() -> datetime:
    """The current UTC time (a function so that tests can replace the clock)."""
    return datetime.now(timezone.utc)


def _date_text_only(value: object) -> object:
    """Only a date text (or a real date) goes on: numbers and booleans are never read as timestamps."""
    if not isinstance(value, (str, datetime)):
        raise ValueError("a date text is required")
    return value


def _inside_observation_window(moment: datetime) -> datetime:
    """Accept only timezone-aware dates from OBSERVATION_RETENTION_DAYS ago to now plus FUTURE_TOLERANCE."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("a time zone is required")
    now = utc_now()
    if not now - timedelta(days=OBSERVATION_RETENTION_DAYS) <= moment <= now + FUTURE_TOLERANCE:
        raise ValueError("date outside the accepted window")
    return moment


def _plain_server_name(name: str) -> str:
    """Refuse a trailing space and invisible characters (zero width joiners, direction marks...)."""
    if name != name.rstrip() or any(unicodedata.category(character) in INVISIBLE_CATEGORIES for character in name):
        raise ValueError("invisible or trailing blank characters")
    return name


def _known_lot_size(size: int) -> int:
    """Accept only the lot sizes the game sells (strict mode already refuses booleans and floats)."""
    if size not in LOT_SIZES:
        raise ValueError("unknown lot size")
    return size


LotSize = Annotated[int, AfterValidator(_known_lot_size)]
# Not strict on purpose: the web framework hands over JSON dates as text, which strict mode refuses; the
# BeforeValidator keeps everything but text out and the AfterValidator demands a time zone.
ObservationTime = Annotated[datetime, Field(strict=False), BeforeValidator(_date_text_only),
                            AfterValidator(_inside_observation_window)]
ServerName = Annotated[str, Field(pattern=SERVER_NAME_PATTERN, max_length=MAX_SERVER_NAME_LENGTH),
                       AfterValidator(_plain_server_name)]


class Reading(BaseModel):
    """One price observation: the total price of a lot of an item on a game server."""

    model_config = STRICT_MODEL

    server: ServerName
    item_id: int = Field(ge=1, le=MAX_ITEM_ID)
    lot_size: LotSize
    price: int = Field(ge=1, le=MAX_PRICE)
    observed_at: ObservationTime


class ReadingBatch(BaseModel):
    """A batch of readings, never empty and never above MAX_BATCH_READINGS."""

    model_config = STRICT_MODEL

    readings: list[Reading] = Field(min_length=1, max_length=MAX_BATCH_READINGS)


class KeyIdRequest(BaseModel):
    """The key to revoke (the 11 characters between the dots of a key) and whether to delete its readings."""

    model_config = STRICT_MODEL

    key_id: str = Field(pattern=KEY_ID_PATTERN)
    purge: bool = False
