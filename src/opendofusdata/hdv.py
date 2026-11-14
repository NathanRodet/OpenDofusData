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
    decode_fields,
    first_field,
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


def _pair_with_sizes(item_id: int, prices: list[int], server: str, captured_at: str) -> list[LotPrice]:
    """Pair prices with lot sizes in order; a zero price means no lot of that size."""
    return [LotPrice(item_id, server, lot_size, price, captured_at)
            for lot_size, price in zip(LOT_SIZES, prices) if price != NO_LOT_PRICE]


def _entry_prices(entry: bytes) -> tuple[int | None, list[int]]:
    detail = decode_fields(entry)
    packed = first_field(detail, LOT_PRICES_FIELD, WIRE_TYPE_LENGTH_DELIMITED)
    return first_field(detail, LOT_ITEM_FIELD, WIRE_TYPE_VARINT), (unpack_varints(packed) if isinstance(packed, bytes) else [])


def _cheapest_by_size(columns: list[list[int]]) -> list[int]:
    """Per lot size, the lowest non-zero price over all entries (equipment has one entry per offer)."""
    width = max((len(prices) for prices in columns), default=0)
    cheapest = []
    for index in range(width):
        offered = [prices[index] for prices in columns if index < len(prices) and prices[index] != NO_LOT_PRICE]
        cheapest.append(min(offered) if offered else NO_LOT_PRICE)
    return cheapest


def _read_lot_message(payload: bytes) -> tuple[int | None, list[int]]:
    """Return (item id, prices by lot size); the field 1 entry is repeated for equipment, one per offer."""
    outer = decode_fields(payload)
    entries = [value for number, wire_type, value in outer
               if number == LOT_DETAIL_FIELD and wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes)]
    item_id, columns = None, []
    for entry in entries:
        entry_item, prices = _entry_prices(entry)
        item_id = item_id if item_id is not None else entry_item
        columns.append(prices)
    if item_id is None:
        item_id = first_field(outer, LOT_FALLBACK_ITEM_FIELD, WIRE_TYPE_VARINT)
    return (item_id if isinstance(item_id, int) else None), _cheapest_by_size(columns)


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
