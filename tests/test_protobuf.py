import pytest

from opendofusdata.protobuf import (
    DecodeError,
    decode_fields,
    read_varint,
    to_signed,
    try_decode_fields,
    zigzag_decode,
)


def test_read_varint_multibyte() -> None:
    assert read_varint(b"\xac\x02", 0) == (300, 2)


def test_read_varint_with_offset() -> None:
    assert read_varint(b"\xff\x05", 1) == (5, 2)


def test_decode_fields_mixed_types() -> None:
    assert decode_fields(bytes.fromhex("08960112024869")) == [(1, 0, 150), (2, 2, b"Hi")]


def test_decode_fields_empty() -> None:
    assert decode_fields(b"") == []


def test_decode_fixed_widths_little_endian() -> None:
    data = b"\x09" + (1).to_bytes(8, "little") + b"\x15" + (258).to_bytes(4, "little")
    assert decode_fields(data) == [(1, 1, 1), (2, 5, 258)]


def test_truncated_varint_raises_decode_error() -> None:
    with pytest.raises(DecodeError):
        read_varint(b"\x80", 0)
    with pytest.raises(DecodeError):
        decode_fields(b"\x08\x80")


def test_overlong_varint_raises_decode_error() -> None:
    with pytest.raises(DecodeError):
        read_varint(b"\x80" * 10 + b"\x01", 0)


def test_truncated_length_delimited_raises_decode_error() -> None:
    with pytest.raises(DecodeError):
        decode_fields(b"\x12\x05Hi")


def test_truncated_fixed_raises_decode_error() -> None:
    with pytest.raises(DecodeError):
        decode_fields(b"\x09\x01\x02")


def test_unknown_wire_type_raises_decode_error() -> None:
    for tag in (0x0B, 0x0C, 0x0F):
        with pytest.raises(DecodeError):
            decode_fields(bytes([tag]))


def test_field_number_zero_raises_decode_error() -> None:
    with pytest.raises(DecodeError):
        decode_fields(b"\x00\x01")


def test_try_decode_fields_returns_none_on_garbage() -> None:
    assert try_decode_fields(b"\xff\xff\xff") is None


def test_try_decode_fields_returns_fields() -> None:
    assert try_decode_fields(b"\x08\x01") == [(1, 0, 1)]


def test_zigzag_decode() -> None:
    assert zigzag_decode(1) == -1
    assert zigzag_decode(2) == 1
    assert zigzag_decode(0) == 0


def test_to_signed() -> None:
    assert to_signed(2**64 - 1) == -1
    assert to_signed(5) == 5
