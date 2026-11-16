"""The strict schemas of the readings: types, bounds, characters and the date window."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from keyserver import schemas
from keyserver.schemas import (
    EARLIEST_OBSERVATION, FUTURE_TOLERANCE, MAX_BATCH_READINGS, MAX_ITEM_ID, MAX_SERVER_NAME_LENGTH, Reading,
    ReadingBatch,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schemas, "utc_now", lambda: NOW)


def reading_json(**changes: object) -> str:
    fields: dict[str, object] = {"server": "Brâkmar", "item_id": 1234, "observed_at": "2026-11-15T10:00:00Z"}
    fields.update(changes)
    return json.dumps(fields)


def refused(**changes: object) -> bool:
    try:
        Reading.model_validate_json(reading_json(**changes))
    except ValidationError:
        return True
    return False


def test_constants_are_the_planned_ones() -> None:
    assert (MAX_BATCH_READINGS, MAX_SERVER_NAME_LENGTH, MAX_ITEM_ID) == (2000, 40, 10_000_000)
    assert EARLIEST_OBSERVATION == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert FUTURE_TOLERANCE == timedelta(minutes=5)


@pytest.mark.parametrize("server", ["Brâkmar", "Pandala-1", "Ily", "Server 2", "A", "x" * 40])
def test_valid_reading_is_accepted(server: str) -> None:
    reading = Reading.model_validate_json(reading_json(server=server))
    assert reading.server == server and reading.item_id == 1234


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Reading.model_validate_json(json.dumps({"server": "Ily", "item_id": 1, "observed_at": "2026-11-15T10:00:00Z",
                                                "extra": 1}))


@pytest.mark.parametrize("changes", [
    {"item_id": "12"}, {"item_id": True}, {"item_id": 1.5}, {"item_id": None},
    {"server": 12}, {"server": None},
    {"observed_at": "2026-11-15T10:00:00"}, {"observed_at": 1_700_000_000}, {"observed_at": "pas une date"},
])
def test_wrong_types_are_rejected(changes: dict[str, object]) -> None:
    assert refused(**changes)


@pytest.mark.parametrize("server", [
    "a\nb", "a\x00b", "a'b", "a;b", "<b>", " a", "", "x" * 41, "a\tb", "a\r", "-a", "_a", "a\"b", "a/b", "a\\b",
    "a%b", "a`b", "a$b",
])
def test_server_name_rejects_control_characters_and_sql_or_markup_characters(server: str) -> None:
    assert refused(server=server)


def test_a_trailing_line_feed_is_rejected() -> None:
    assert refused(server="Ily\n")


@pytest.mark.parametrize("item_id, valid", [(0, False), (-1, False), (1, True), (MAX_ITEM_ID, True), (MAX_ITEM_ID + 1, False)])
def test_item_id_bounds(item_id: int, valid: bool) -> None:
    assert refused(item_id=item_id) is (not valid)


@pytest.mark.parametrize("moment, valid", [
    ("2019-12-31T23:59:59Z", False), ("2020-01-01T00:00:00Z", True), ("2026-11-15T12:00:00Z", True),
    ("2026-11-15T12:05:00Z", True), ("2026-11-15T12:05:01Z", False), ("3000-01-01T00:00:00Z", False),
    ("2026-11-15T14:00:00+02:00", True), ("2026-11-15T15:00:00+02:00", False),
])
def test_observed_at_window(moment: str, valid: bool) -> None:
    assert refused(observed_at=moment) is (not valid)


@pytest.mark.parametrize("size, valid", [(0, False), (1, True), (MAX_BATCH_READINGS, True), (MAX_BATCH_READINGS + 1, False)])
def test_batch_size_bounds(size: int, valid: bool) -> None:
    readings = [json.loads(reading_json())] * size
    try:
        ReadingBatch.model_validate_json(json.dumps({"readings": readings}))
        accepted = True
    except ValidationError:
        accepted = False
    assert accepted is valid


def test_batch_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ReadingBatch.model_validate_json(json.dumps({"readings": [json.loads(reading_json())], "extra": True}))


@pytest.mark.parametrize("server", ["Brakmar ", "Brakmar\u3000", "a\u200db", "a\u200bb", "a\u2060b", "a\ufeffb", "a\u202eb"])
def test_server_name_rejects_trailing_spaces_and_invisible_characters(server: str) -> None:
    assert refused(server=server)
