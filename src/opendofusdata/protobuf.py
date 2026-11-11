"""Generic (schema-less) Protobuf wire-format decoder: pure logic, stdlib only."""

import logging

logger = logging.getLogger(__name__)

WIRE_TYPE_VARINT = 0
WIRE_TYPE_FIXED64 = 1
WIRE_TYPE_LENGTH_DELIMITED = 2
WIRE_TYPE_FIXED32 = 5

FIXED64_BYTES = 8
FIXED32_BYTES = 4
MAX_VARINT_BYTES = 10
VARINT_PAYLOAD_BITS = 7
VARINT_PAYLOAD_MASK = 0x7F
VARINT_CONTINUATION_BIT = 0x80
WIRE_TYPE_MASK = 0x07
WIRE_TYPE_BITS = 3
UINT64_MODULUS = 2**64
INT64_SIGN_BIT = 2**63

Field = tuple[int, int, int | bytes]


class DecodeError(ValueError):
    """Raised when bytes are not valid Protobuf wire format."""


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Read a varint at offset and return (value, new offset)."""
    value = 0
    for index in range(MAX_VARINT_BYTES):
        position = offset + index
        if position >= len(data):
            raise DecodeError("truncated varint")
        byte = data[position]
        value |= (byte & VARINT_PAYLOAD_MASK) << (VARINT_PAYLOAD_BITS * index)
        if not byte & VARINT_CONTINUATION_BIT:
            return value, position + 1
    raise DecodeError("varint longer than 10 bytes")


def _read_fixed(data: bytes, offset: int, size: int) -> tuple[int, int]:
    end = offset + size
    if end > len(data):
        raise DecodeError("truncated fixed-width value")
    return int.from_bytes(data[offset:end], "little"), end


def _read_length_delimited(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = read_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise DecodeError("truncated length-delimited value")
    return data[offset:end], end


def _read_value(data: bytes, offset: int, wire_type: int) -> tuple[int | bytes, int]:
    if wire_type == WIRE_TYPE_VARINT:
        return read_varint(data, offset)
    if wire_type == WIRE_TYPE_FIXED64:
        return _read_fixed(data, offset, FIXED64_BYTES)
    if wire_type == WIRE_TYPE_LENGTH_DELIMITED:
        return _read_length_delimited(data, offset)
    if wire_type == WIRE_TYPE_FIXED32:
        return _read_fixed(data, offset, FIXED32_BYTES)
    raise DecodeError(f"unsupported wire type {wire_type}")


def decode_fields(data: bytes) -> list[Field]:
    """Decode a message into (field number, wire type, value) tuples."""
    fields: list[Field] = []
    offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field_number = tag >> WIRE_TYPE_BITS
        if field_number == 0:
            raise DecodeError("field number 0 is invalid")
        wire_type = tag & WIRE_TYPE_MASK
        value, offset = _read_value(data, offset, wire_type)
        fields.append((field_number, wire_type, value))
    return fields


def try_decode_fields(data: bytes) -> list[Field] | None:
    """Decode fields, returning None instead of raising on invalid data."""
    try:
        return decode_fields(data)
    except DecodeError:
        logger.debug("not a valid protobuf message (%d bytes)", len(data))
        return None


def to_signed(value: int) -> int:
    """Interpret an unsigned 64-bit value as two's complement."""
    return value - UINT64_MODULUS if value >= INT64_SIGN_BIT else value


def zigzag_decode(value: int) -> int:
    """Decode a ZigZag-encoded integer (sint32/sint64)."""
    return (value >> 1) ^ -(value & 1)


def first_field(fields: list[Field], number: int, wire_type: int) -> int | bytes | None:
    """Value of the first occurrence of a field with the expected wire type."""
    for field_number, field_wire_type, value in fields:
        if field_number == number and field_wire_type == wire_type:
            return value
    return None
