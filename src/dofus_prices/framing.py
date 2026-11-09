"""Extraction of message envelopes from a reassembled TCP byte stream: pure logic."""

import logging
from dataclasses import dataclass
from enum import Enum, auto

from dofus_prices.protobuf import (
    MAX_VARINT_BYTES,
    WIRE_TYPE_LENGTH_DELIMITED,
    DecodeError,
    Field,
    read_varint,
    try_decode_fields,
)

logger = logging.getLogger(__name__)

TYPE_URL_PREFIX = b"type.ankama.com/"
MAX_BUFFER_BYTES = 262144
MAX_FRAME_BYTES = 65536
MAX_NESTING_DEPTH = 4
ANY_TYPE_URL_FIELD = 1
ANY_VALUE_FIELD = 2
FRAME_LOOKBACK_BYTES = MAX_FRAME_BYTES + MAX_VARINT_BYTES


@dataclass
class Envelope:
    """A typed message: the type name (without URL prefix) and its raw payload."""

    type_name: str
    payload: bytes


class FrameStatus(Enum):
    """Outcome of looking for a frame at a given buffer position."""

    COMPLETE = auto()
    INCOMPLETE = auto()
    INVALID = auto()


def _as_envelope(fields: list[Field]) -> Envelope | None:
    """Interpret a decoded message as an Any (type URL + optional payload)."""
    url = next((value for number, wire, value in fields
                if number == ANY_TYPE_URL_FIELD and wire == WIRE_TYPE_LENGTH_DELIMITED), None)
    if not isinstance(url, bytes) or not url.startswith(TYPE_URL_PREFIX):
        return None
    payload = next((value for number, wire, value in fields
                    if number == ANY_VALUE_FIELD and wire == WIRE_TYPE_LENGTH_DELIMITED), b"")
    try:
        type_name = url[len(TYPE_URL_PREFIX):].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return Envelope(type_name, payload if isinstance(payload, bytes) else b"")


def find_envelopes(fields: list[Field], depth: int = 0) -> list[Envelope]:
    """Find every envelope in a decoded message, searching nested messages."""
    envelope = _as_envelope(fields)
    if envelope is not None:
        return [envelope]
    if depth >= MAX_NESTING_DEPTH:
        return []
    found: list[Envelope] = []
    for _number, wire_type, value in fields:
        if wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes):
            children = try_decode_fields(value)
            if children:
                found.extend(find_envelopes(children, depth + 1))
    return found


def _locate_frame(buffer: bytes, position: int) -> tuple[FrameStatus, int, int]:
    """Return (status, body start, body end) of the frame at position."""
    try:
        length, start = read_varint(buffer, position)
    except DecodeError:
        truncated = len(buffer) - position < MAX_VARINT_BYTES
        return (FrameStatus.INCOMPLETE if truncated else FrameStatus.INVALID), 0, 0
    if length == 0 or length > MAX_FRAME_BYTES:
        return FrameStatus.INVALID, 0, 0
    end = start + length
    if end > len(buffer):
        return FrameStatus.INCOMPLETE, 0, 0
    return FrameStatus.COMPLETE, start, end


def _next_prefix(buffer: bytes, position: int, cached: int) -> int:
    """Index of the next type URL prefix at or after position (len if none)."""
    if cached >= position:
        return cached
    index = buffer.find(TYPE_URL_PREFIX, position)
    return len(buffer) if index == -1 else index


def _skip_ahead(buffer: bytes, position: int, cached: int) -> tuple[int, int]:
    """Jump to the first position where a frame holding a type URL can start.

    While unsynchronised a frame is only accepted if it contains the prefix, so
    positions further back than one maximal frame before it cannot start one.
    Incomplete frames are only candidates: the scan goes on past them, and the
    buffer is kept from the first candidate if nothing complete is found.
    """
    prefix_at = _next_prefix(buffer, position, cached)
    return max(position, prefix_at - FRAME_LOOKBACK_BYTES), prefix_at


class EnvelopeExtractor:
    """Incrementally extract envelopes from one direction of a TCP stream."""

    def __init__(self) -> None:
        self._buffer = b""
        self._synchronised = False

    def reset(self) -> None:
        """Forget buffered bytes and the synchronisation state."""
        self._buffer = b""
        self._synchronised = False

    def feed(self, data: bytes) -> list[Envelope]:
        """Append stream bytes and return the envelopes of all complete frames."""
        buffer = self._buffer + data
        if len(buffer) > MAX_BUFFER_BYTES:
            logger.warning("buffer overflow, dropping oldest bytes")
            buffer = buffer[-MAX_BUFFER_BYTES:]
            self._synchronised = False
        envelopes, position = self._scan(buffer)
        self._buffer = buffer[position:]
        return envelopes

    def _scan(self, buffer: bytes) -> tuple[list[Envelope], int]:
        """Return the envelopes and the offset of the first unconsumed byte."""
        envelopes: list[Envelope] = []
        position, prefix_at, pending = 0, -1, None
        while position < len(buffer):
            if not self._synchronised:
                position, prefix_at = _skip_ahead(buffer, position, prefix_at)
            status, found, end = self._try_frame(buffer, position)
            if status is FrameStatus.COMPLETE:
                envelopes.extend(found)
                position, pending = end, None
                continue
            if status is FrameStatus.INCOMPLETE:
                pending = position if pending is None else pending
                if self._synchronised:
                    break
            self._synchronised = self._synchronised and status is FrameStatus.INCOMPLETE
            position += 1
        return envelopes, len(buffer) if pending is None else pending

    def _try_frame(
        self, buffer: bytes, position: int
    ) -> tuple[FrameStatus, list[Envelope], int]:
        status, start, end = _locate_frame(buffer, position)
        if status is not FrameStatus.COMPLETE:
            return status, [], 0
        fields = try_decode_fields(buffer[start:end])
        envelopes = find_envelopes(fields) if fields else []
        if not fields or (not envelopes and not self._synchronised):
            return FrameStatus.INVALID, [], 0
        self._synchronised = True
        return FrameStatus.COMPLETE, envelopes, end
