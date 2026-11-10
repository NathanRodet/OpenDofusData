"""Synthetic jzs (lot prices) and ire (market stats) envelopes shared by tests."""

from datetime import datetime, timezone

from dofus_prices.framing import Envelope

REAL_PACKED_PRICES = bytes.fromhex("ee05ec2dc986039fc21e")  # item 307: 750, 5868, 49993, 499999
STATS_ITEM_ID = 376
LAST_SALE = datetime(2026, 11, 9, 10, 50, 9, tzinfo=timezone.utc)
CONTINUATION = 0x80
PAYLOAD_MASK = 0x7F
PAYLOAD_BITS = 7
FLOW_KEY = ("1.2.3.4", 5555, "5.6.7.8", 40000)


def varint(value: int) -> bytes:
    out = bytearray()
    while value > PAYLOAD_MASK:
        out.append((value & PAYLOAD_MASK) | CONTINUATION)
        value >>= PAYLOAD_BITS
    out.append(value)
    return bytes(out)


def int_field(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(value)


def bytes_field(number: int, value: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(value)) + value


def lot_envelope(item: int = 307, packed: bytes = REAL_PACKED_PRICES) -> Envelope:
    detail = int_field(1, item) + bytes_field(2, packed) + int_field(3, 1) + int_field(4, 2)
    return Envelope("jzs", bytes_field(1, detail) + int_field(2, 5))


def stats_envelope(prices: tuple[int, ...] = (91998, 25000)) -> Envelope:
    text = LAST_SALE.strftime("%Y-%m-%dT%H:%M:%S.901212706Z").encode()
    points = [int_field(1, price) + int_field(2, STATS_ITEM_ID) + bytes_field(3, text) + int_field(4, 1)
              for price in prices]
    return Envelope("ire", b"".join(bytes_field(1, point) for point in points))
