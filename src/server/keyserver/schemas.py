"""Strict schemas of the readings sent by the clients: types, bounds, characters and dates."""

import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

MAX_BATCH_READINGS = 2000
MAX_SERVER_NAME_LENGTH = 40
MAX_ITEM_ID = 10_000_000
EARLIEST_OBSERVATION = datetime(2020, 1, 1, tzinfo=timezone.utc)
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


def _inside_observation_window(moment: datetime) -> datetime:
    """Accept only timezone-aware dates between EARLIEST_OBSERVATION and now plus FUTURE_TOLERANCE."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("a time zone is required")
    if not EARLIEST_OBSERVATION <= moment <= utc_now() + FUTURE_TOLERANCE:
        raise ValueError("date outside the accepted window")
    return moment


def _plain_server_name(name: str) -> str:
    """Refuse a trailing space and invisible characters (zero width joiners, direction marks...)."""
    if name != name.rstrip() or any(unicodedata.category(character) in INVISIBLE_CATEGORIES for character in name):
        raise ValueError("invisible or trailing blank characters")
    return name


ObservationTime = Annotated[datetime, AfterValidator(_inside_observation_window)]
ServerName = Annotated[str, Field(pattern=SERVER_NAME_PATTERN, max_length=MAX_SERVER_NAME_LENGTH),
                       AfterValidator(_plain_server_name)]


class Reading(BaseModel):
    """One observation; the fields of each category (prices, quantities, runes) come with the ingestion."""

    model_config = STRICT_MODEL

    server: ServerName
    item_id: int = Field(ge=1, le=MAX_ITEM_ID)
    observed_at: ObservationTime


class ReadingBatch(BaseModel):
    """A batch of readings, never empty and never above MAX_BATCH_READINGS."""

    model_config = STRICT_MODEL

    readings: list[Reading] = Field(min_length=1, max_length=MAX_BATCH_READINGS)


class KeyIdRequest(BaseModel):
    """The identifier of the key to revoke (the 11 characters between the dots of a key)."""

    model_config = STRICT_MODEL

    key_id: str = Field(pattern=KEY_ID_PATTERN)
