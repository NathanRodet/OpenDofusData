"""Decoding of HDV lot price messages: pure logic."""

import logging

from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    LOT_DETAIL_FIELD,
    LOT_FALLBACK_ITEM_FIELD,
    LOT_ITEM_FIELD,
    LOT_PRICES_FIELD,
    LOT_RESPONSE_TYPE,
)
from opendofusdata.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    WIRE_TYPE_VARINT,
    DecodeError,
    Field,
    decode_fields,
    read_varint,
)
from opendofusdata.records import LOT_SIZES, LotPrice

logger = logging.getLogger(__name__)

NO_LOT_PRICE = 0


def unpack_varints(data: bytes) -> list[int]:
    """Decode consecutive varints until the end of the data."""
    values: list[int] = []
    offset = 0
    while offset < len(data):
        value, offset = read_varint(data, offset)
        values.append(value)
    return values


def _first_field(fields: list[Field], number: int, wire_type: int) -> int | bytes | None:
    """Value of the first occurrence of a field with the expected wire type."""
    for field_number, field_wire_type, value in fields:
        if field_number == number and field_wire_type == wire_type:
            return value
    return None


def _find_item_id(detail: list[Field], outer: list[Field]) -> int | None:
    """Item id from the detail message, else from the outer message."""
    item_id = _first_field(detail, LOT_ITEM_FIELD, WIRE_TYPE_VARINT)
    if item_id is None:
        item_id = _first_field(outer, LOT_FALLBACK_ITEM_FIELD, WIRE_TYPE_VARINT)
    return item_id if isinstance(item_id, int) else None


def _pair_with_sizes(item_id: int, prices: list[int], server: str, captured_at: str) -> list[LotPrice]:
    """Pair prices with lot sizes in order; a zero price means no lot of that size."""
    return [LotPrice(item_id, server, lot_size, price, captured_at)
            for lot_size, price in zip(LOT_SIZES, prices) if price != NO_LOT_PRICE]


def _read_lot_message(payload: bytes) -> tuple[int | None, list[int]]:
    """Return (item id, packed prices); prices are empty when the field is absent."""
    outer = decode_fields(payload)
    detail_bytes = _first_field(outer, LOT_DETAIL_FIELD, WIRE_TYPE_LENGTH_DELIMITED)
    detail = decode_fields(detail_bytes) if isinstance(detail_bytes, bytes) else []
    packed = _first_field(detail, LOT_PRICES_FIELD, WIRE_TYPE_LENGTH_DELIMITED)
    prices = unpack_varints(packed) if isinstance(packed, bytes) else []
    return _find_item_id(detail, outer), prices


def decode_lot_prices(envelope: Envelope, server: str, captured_at: str) -> list[LotPrice]:
    """Decode a lot price response; return an empty list for anything else or invalid."""
    if envelope.type_name != LOT_RESPONSE_TYPE:
        return []
    try:
        item_id, prices = _read_lot_message(envelope.payload)
    except DecodeError as error:
        logger.warning("unreadable %s message: %s", envelope.type_name, error)
        return []
    if item_id is None:
        logger.warning("%s message without item id, skipped", envelope.type_name)
        return []
    if len(prices) > len(LOT_SIZES):
        logger.warning("%s message with %d prices, skipped", envelope.type_name, len(prices))
        return []
    return _pair_with_sizes(item_id, prices, server, captured_at)
