"""Decoding of HDV market statistics messages: pure logic."""

import logging
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from dofus_prices.framing import Envelope
from dofus_prices.messages import (
    POINT_ITEM_FIELD,
    POINT_PRICE_FIELD,
    POINT_QUANTITY_FIELD,
    POINT_TIMESTAMP_FIELD,
    STATS_DAILY_POINTS_FIELD,
    STATS_HOURLY_POINTS_FIELD,
    STATS_RESPONSE_TYPE,
)
from dofus_prices.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    WIRE_TYPE_VARINT,
    DecodeError,
    Field,
    decode_fields,
    to_signed,
)
from dofus_prices.records import MarketStats
from dofus_prices.timeutil import STORED_TIMESTAMP_FORMAT, format_utc, parse_server_timestamp

logger = logging.getLogger(__name__)

SEVEN_DAYS = timedelta(days=7)


class SamplePoint(NamedTuple):
    """One statistics point of the market curve."""

    item_id: int
    moment: datetime
    price: int
    quantity: int


def _required(fields: list[Field], number: int, wire_type: int) -> int | bytes:
    """Value of the first matching field; ValueError when it is missing."""
    for field_number, field_wire_type, value in fields:
        if field_number == number and field_wire_type == wire_type:
            return value
    raise ValueError(f"missing field {number} with wire type {wire_type}")


def _required_count(fields: list[Field], number: int) -> int:
    """A varint field that must not look negative."""
    value = _required(fields, number, WIRE_TYPE_VARINT)
    if to_signed(value) < 0:
        raise ValueError(f"negative value in field {number}")
    return value


def _read_point(data: bytes) -> SamplePoint:
    """Decode one point sub-message; ValueError (or DecodeError) when invalid."""
    fields = decode_fields(data)
    text = _required(fields, POINT_TIMESTAMP_FIELD, WIRE_TYPE_LENGTH_DELIMITED)
    moment = parse_server_timestamp(text.decode("ascii", errors="replace"))
    return SamplePoint(
        _required_count(fields, POINT_ITEM_FIELD), moment,
        _required_count(fields, POINT_PRICE_FIELD), _required_count(fields, POINT_QUANTITY_FIELD),
    )


def _collect_points(fields: list[Field], number: int) -> list[SamplePoint]:
    """Valid points of one list field, sorted by time; invalid ones are logged and skipped."""
    points: list[SamplePoint] = []
    for field_number, wire_type, value in fields:
        if field_number != number or wire_type != WIRE_TYPE_LENGTH_DELIMITED:
            continue
        try:
            points.append(_read_point(value))
        except ValueError as error:
            logger.warning("skipped invalid point in %s message: %s", STATS_RESPONSE_TYPE, error)
    return sorted(points, key=lambda point: point.moment)


def _value_at_rank(price_counts: list[tuple[int, int]], rank: int) -> int:
    """Price at a 0-based rank of the multiset, walking cumulative counts."""
    seen = 0
    for price, count in sorted(price_counts):
        seen += count
        if rank < seen:
            return price
    raise ValueError("rank beyond total quantity")


def _weighted_median(price_counts: list[tuple[int, int]], total: int) -> int:
    """Median of the multiset where each price is repeated count times."""
    low = _value_at_rank(price_counts, (total - 1) // 2)
    high = _value_at_rank(price_counts, total // 2)
    return (low + high) // 2


def _build_stats(item_id: int, server: str, period: str, points: list[SamplePoint],
                 last_purchase: datetime, captured_at: str) -> MarketStats | None:
    """Statistics of one period; None when no quantity was sold."""
    total = sum(point.quantity for point in points)
    if total == 0:
        return None
    price_counts = [(point.price, point.quantity) for point in points]
    mean = sum(price * count for price, count in price_counts) // total
    curve = [(int(point.moment.timestamp()), point.price, point.quantity) for point in points]
    return MarketStats(item_id, server, period, curve, _weighted_median(price_counts, total),
                       mean, total, captured_at, format_utc(last_purchase), captured_at)


def _window_anchor(daily: list[SamplePoint], captured_at: str) -> datetime:
    """Capture moment; the last daily point when captured_at is unparsable."""
    try:
        return datetime.strptime(captured_at, STORED_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("unparsable captured_at %r, 7d window anchored on the last daily point",
                       captured_at)
        return daily[-1].moment


def _seven_day_points(daily: list[SamplePoint], captured_at: str) -> list[SamplePoint]:
    """Daily points from midnight UTC of (capture date - 7 days), inclusive."""
    if not daily:
        return []
    anchor = _window_anchor(daily, captured_at)
    start = (anchor - SEVEN_DAYS).replace(hour=0, minute=0, second=0, microsecond=0)
    return [point for point in daily if point.moment >= start]


def _build_all_periods(hourly: list[SamplePoint], daily: list[SamplePoint],
                       server: str, captured_at: str) -> list[MarketStats]:
    """Statistics of the 24h, 7d and 30d periods, omitting empty ones."""
    item_id = (hourly or daily)[0].item_id
    last_purchase = (hourly or daily)[-1].moment
    periods = (("24h", hourly), ("7d", _seven_day_points(daily, captured_at)), ("30d", daily))
    built = [_build_stats(item_id, server, period, points, last_purchase, captured_at)
             for period, points in periods if points]
    return [stats for stats in built if stats is not None]


def decode_market_stats(envelope: Envelope, server: str, captured_at: str) -> list[MarketStats]:
    """Decode a market statistics response; return an empty list for anything else or invalid."""
    if envelope.type_name != STATS_RESPONSE_TYPE:
        return []
    try:
        fields = decode_fields(envelope.payload)
    except DecodeError as error:
        logger.warning("unreadable %s message: %s", envelope.type_name, error)
        return []
    hourly = _collect_points(fields, STATS_HOURLY_POINTS_FIELD)
    daily = _collect_points(fields, STATS_DAILY_POINTS_FIELD)
    item_ids = {point.item_id for point in hourly + daily}
    if len(item_ids) > 1:
        logger.warning("%s message mixing items %s, skipped", envelope.type_name, sorted(item_ids))
    if len(item_ids) != 1:
        return []
    return _build_all_periods(hourly, daily, server, captured_at)
