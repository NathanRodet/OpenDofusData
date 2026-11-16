"""The strict schemas of the readings: types, bounds, characters and the date window."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from keyserver import schemas
from keyserver.schemas import (
    FUTURE_TOLERANCE, OBSERVATION_RETENTION_DAYS, LOT_SIZES, MAX_BATCH_READINGS, MAX_ITEM_ID, MAX_PRICE,
    MAX_QUERY_INTEGER, MAX_SERVER_NAME_LENGTH, KeyIdRequest, Reading, ReadingBatch,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schemas, "utc_now", lambda: NOW)


def reading_json(**changes: object) -> str:
    fields: dict[str, object] = {"server": "Brâkmar", "item_id": 1234, "lot_size": 10, "price": 750,
                                 "observed_at": "2026-11-15T10:00:00Z"}
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
    assert (LOT_SIZES, MAX_PRICE, MAX_QUERY_INTEGER) == ((1, 10, 100, 1000), 1_000_000_000_000, 999_999_999_999)
    assert OBSERVATION_RETENTION_DAYS == 14
    assert FUTURE_TOLERANCE == timedelta(minutes=5)


@pytest.mark.parametrize("server", ["Brâkmar", "Pandala-1", "Ily", "Server 2", "A", "x" * 40])
def test_valid_reading_is_accepted(server: str) -> None:
    reading = Reading.model_validate_json(reading_json(server=server))
    assert reading.server == server and reading.item_id == 1234


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Reading.model_validate_json(reading_json(extra=1))


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
    ("2026-11-01T11:59:59Z", False), ("2026-11-01T12:00:00Z", True), ("2026-11-15T12:00:00Z", True),
    ("2020-01-01T00:00:00Z", False), ("2019-12-31T23:59:59Z", False),
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


@pytest.mark.parametrize("lot_size, valid", [
    (1, True), (10, True), (100, True), (1000, True), (0, False), (2, False), (5, False), (1001, False),
    (-1, False), ("10", False), (True, False), (10.0, False),
])
def test_lot_size_bounds(lot_size: object, valid: bool) -> None:
    assert refused(lot_size=lot_size) is (not valid)


@pytest.mark.parametrize("price, valid", [
    (1, True), (MAX_PRICE, True), (0, False), (-5, False), (MAX_PRICE + 1, False), (1.5, False), ("750", False),
    (True, False), (None, False),
])
def test_price_bounds(price: object, valid: bool) -> None:
    assert refused(price=price) is (not valid)


def test_price_and_lot_size_are_required() -> None:
    fields = json.loads(reading_json())
    for name in ("price", "lot_size"):
        with pytest.raises(ValidationError):
            Reading.model_validate_json(json.dumps({key: value for key, value in fields.items() if key != name}))


def test_key_id_request_purge_defaults_to_false() -> None:
    assert KeyIdRequest.model_validate_json('{"key_id": "AAAAAAAAAAA"}').purge is False


def test_key_id_request_purge_true_is_accepted() -> None:
    assert KeyIdRequest.model_validate_json('{"key_id": "AAAAAAAAAAA", "purge": true}').purge is True


@pytest.mark.parametrize("purge", ['"true"', "1", "0", "null", '"yes"'])
def test_key_id_request_purge_must_be_a_real_boolean(purge: str) -> None:
    with pytest.raises(ValidationError):
        KeyIdRequest.model_validate_json('{"key_id": "AAAAAAAAAAA", "purge": %s}' % purge)


def test_python_mode_accepts_a_date_text_like_the_web_framework_passes_it() -> None:
    reading = Reading.model_validate(json.loads(reading_json()))
    assert reading.observed_at == datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("moment", [1_700_000_000, 1.7e9, True, None, ["2026-11-15T10:00:00Z"], "2026-11-15",
                                    "2026-11-15T10:00:00"])
def test_python_mode_still_refuses_anything_but_a_timezone_aware_date_text(moment: object) -> None:
    with pytest.raises(ValidationError):
        Reading.model_validate(json.loads(reading_json(observed_at=moment)))
