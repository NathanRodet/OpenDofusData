"""Tests for HDV lot price decoding, on synthetic envelopes built from real captured bytes."""

import logging

import pytest

from opendofusdata.framing import Envelope
from opendofusdata.hdv import decode_lot_prices, unpack_varints
from opendofusdata.protobuf import DecodeError
from opendofusdata.storage import LotPrice

SERVER = "Test"
CAPTURED_AT = "2026-11-10T12:00:00Z"
UNKNOWN_FIELD = 9
LENGTH_DELIMITED_TAG_BITS = 2
VARINT_TAG_BITS = 0
CONTINUATION = 0x80
PAYLOAD_MASK = 0x7F
PAYLOAD_BITS = 7


def varint(value: int) -> bytes:
    out = bytearray()
    while value > PAYLOAD_MASK:
        out.append((value & PAYLOAD_MASK) | CONTINUATION)
        value >>= PAYLOAD_BITS
    out.append(value)
    return bytes(out)


def int_field(number: int, value: int) -> bytes:
    return varint((number << 3) | VARINT_TAG_BITS) + varint(value)


def bytes_field(number: int, value: bytes) -> bytes:
    return varint((number << 3) | LENGTH_DELIMITED_TAG_BITS) + varint(len(value)) + value


def lot_envelope(item: int | None, packed: bytes | None, outer_item: int | None = None) -> Envelope:
    detail = b"" if item is None else int_field(1, item)
    if packed is not None:
        detail += bytes_field(2, packed)
    detail += int_field(3, 1) + int_field(4, 2)
    payload = bytes_field(1, detail) + int_field(2, 5)
    if outer_item is not None:
        payload += int_field(3, outer_item)
    return Envelope(type_name="jzs", payload=payload)


def decode(envelope: Envelope) -> list[LotPrice]:
    return decode_lot_prices(envelope, SERVER, CAPTURED_AT)


def as_tuples(lots: list[LotPrice]) -> list[tuple[int, int, int]]:
    return [(lot.item_id, lot.lot_size, lot.price) for lot in lots]


def test_decodes_four_lot_prices_for_item_307() -> None:
    lots = decode(lot_envelope(307, bytes.fromhex("ee05ec2dc986039fc21e")))
    assert as_tuples(lots) == [(307, 1, 750), (307, 10, 5868), (307, 100, 49993), (307, 1000, 499999)]
    assert lots[0] == LotPrice(307, SERVER, 1, 750, CAPTURED_AT)


def test_zero_price_means_no_lot_of_that_size() -> None:
    lots = decode(lot_envelope(376, bytes.fromhex("9101d00ebd6500")))
    assert as_tuples(lots) == [(376, 1, 145), (376, 10, 1872), (376, 100, 12989)]


def test_single_lot_item() -> None:
    lots = decode(lot_envelope(34095, bytes.fromhex("a98805000000")))
    assert as_tuples(lots) == [(34095, 1, 82985)]


def test_item_id_falls_back_to_outer_field() -> None:
    lots = decode(lot_envelope(None, bytes.fromhex("a98805000000"), outer_item=34095))
    assert as_tuples(lots) == [(34095, 1, 82985)]


def test_missing_item_id_returns_empty_list_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert decode(lot_envelope(None, bytes.fromhex("a98805"))) == []
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_unrelated_envelope_returns_empty_list() -> None:
    assert decode(Envelope(type_name="ire", payload=b"")) == []


def test_more_than_four_prices_is_rejected_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert decode(lot_envelope(307, bytes([1, 2, 3, 4, 5]))) == []
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_truncated_packed_prices_are_skipped_without_raising(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert decode(lot_envelope(307, bytes.fromhex("ee05ec"))) == []
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_missing_prices_field_returns_empty_list() -> None:
    assert decode(lot_envelope(307, None)) == []


def test_unpack_varints_roundtrip() -> None:
    values = [0, 1, 127, 128, 750, 499999]
    assert unpack_varints(b"".join(varint(value) for value in values)) == values
    assert unpack_varints(b"") == []


def test_unpack_varints_rejects_truncated_input() -> None:
    with pytest.raises(DecodeError):
        unpack_varints(bytes.fromhex("ee05ec"))
