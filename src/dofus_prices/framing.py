"""Extraction of message envelopes from a reassembled TCP byte stream: pure logic."""

import heapq
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
    """A typed message: type name (without URL prefix) and raw payload."""
    type_name: str
    payload: bytes


class FrameStatus(Enum):
    COMPLETE = auto()
    INCOMPLETE = auto()
    INVALID = auto()


def _as_envelope(fields: list[Field]) -> Envelope | None:
    """Interpret a decoded message as an Any (type URL + optional payload)."""
    by_number = {number: value for number, wire, value in reversed(fields)
                 if wire == WIRE_TYPE_LENGTH_DELIMITED}
    url = by_number.get(ANY_TYPE_URL_FIELD)
    if not isinstance(url, bytes) or not url.startswith(TYPE_URL_PREFIX):
        return None
    payload = by_number.get(ANY_VALUE_FIELD, b"")
    try:
        name = url[len(TYPE_URL_PREFIX):].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return Envelope(name, payload if isinstance(payload, bytes) else b"")


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
            found.extend(find_envelopes(try_decode_fields(value) or [], depth + 1))
    return found


def _locate_frame(buffer: bytearray, position: int) -> tuple[FrameStatus, int, int]:
    """Return (status, body start, end); for INCOMPLETE, end is the length needed."""
    try:
        length, start = read_varint(buffer, position)
    except DecodeError:
        truncated = len(buffer) - position < MAX_VARINT_BYTES
        return (FrameStatus.INCOMPLETE if truncated else FrameStatus.INVALID), 0, len(buffer) + 1
    if not 0 < length <= MAX_FRAME_BYTES:
        return FrameStatus.INVALID, 0, 0
    end = start + length
    return (FrameStatus.INCOMPLETE if end > len(buffer) else FrameStatus.COMPLETE), start, end


class EnvelopeExtractor:
    """Extract envelopes from one TCP stream direction (absolute offsets).

    Unsynchronised, an incomplete frame is only a candidate kept in a heap by the
    length it needs, so each position is examined once (linear work)."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Forget buffered bytes and the synchronisation state."""
        self._buffer = bytearray()
        self._base, self._cursor = 0, 0
        self._candidates: list[tuple[int, int]] = []
        self._prefix_at, self._searched_until = -1, 0
        self._synchronised = False

    @property
    def buffered_bytes(self) -> int:
        """Number of stream bytes currently held in the internal buffer."""
        return len(self._buffer)

    @property
    def _end(self) -> int:
        return self._base + len(self._buffer)

    def feed(self, data: bytes) -> list[Envelope]:
        """Append stream bytes and return the envelopes of all complete frames."""
        self._buffer += data
        if len(self._buffer) > MAX_BUFFER_BYTES:
            logger.warning("buffer overflow, dropping oldest bytes")
            self._discard_before(self._end - MAX_BUFFER_BYTES)
            self._cursor = max(self._cursor, self._base)
            self._synchronised = False
        envelopes: list[Envelope] = []
        while self._cursor < self._end:
            step = self._advance()
            if step is None:
                break
            envelopes.extend(step)
        self._trim()
        return envelopes

    def _trim(self) -> None:
        keep_from = self._cursor if self._synchronised else self._end - FRAME_LOOKBACK_BYTES
        if keep_from - self._base >= MAX_FRAME_BYTES:
            self._discard_before(keep_from)

    def _discard_before(self, position: int) -> None:
        del self._buffer[: position - self._base]
        self._base = position

    def _advance(self) -> list[Envelope] | None:
        """Make one step; return None when more data is needed to continue."""
        if not self._synchronised:
            return self._advance_unsynchronised()
        status, found, bound = self._try_frame(self._cursor)
        if status is FrameStatus.INCOMPLETE:
            return None
        self._synchronised = status is FrameStatus.COMPLETE
        self._cursor = bound if self._synchronised else self._cursor + 1
        return found

    def _advance_unsynchronised(self) -> list[Envelope]:
        ready = self._retry_ready_candidates()
        if ready is not None:
            return ready
        self._cursor = max(self._cursor, self._next_prefix() - FRAME_LOOKBACK_BYTES)
        status, found, bound = self._try_frame(self._cursor)
        if status is FrameStatus.COMPLETE:
            return self._accept(found, bound)
        if status is FrameStatus.INCOMPLETE:
            heapq.heappush(self._candidates, (bound, self._cursor))
        self._cursor += 1
        return []

    def _retry_ready_candidates(self) -> list[Envelope] | None:
        """Retry candidates whose frame is now fully buffered, earliest first."""
        ready: list[int] = []
        while self._candidates and self._candidates[0][0] <= self._end:
            ready.append(heapq.heappop(self._candidates)[1])
        for start in sorted(ready):
            status, found, bound = self._try_frame(start)
            if status is FrameStatus.COMPLETE:
                return self._accept(found, bound)
            if status is FrameStatus.INCOMPLETE:
                heapq.heappush(self._candidates, (bound, start))
        return None

    def _accept(self, found: list[Envelope], end: int) -> list[Envelope]:
        self._synchronised = True
        self._cursor = end
        self._candidates.clear()
        return found

    def _next_prefix(self) -> int:
        """Absolute index of the next type URL prefix (buffer end if none)."""
        if self._prefix_at >= self._cursor:
            return self._prefix_at
        start = max(self._cursor, self._searched_until) - self._base
        index = self._buffer.find(TYPE_URL_PREFIX, start)
        if index == -1:
            self._searched_until = self._end - len(TYPE_URL_PREFIX) + 1
            return self._end
        self._prefix_at = self._base + index
        return self._prefix_at

    def _try_frame(self, position: int) -> tuple[FrameStatus, list[Envelope], int]:
        """Examine the frame at an absolute position."""
        status, start, end = _locate_frame(self._buffer, position - self._base)
        if status is not FrameStatus.COMPLETE:
            return status, [], self._base + end
        fields = try_decode_fields(bytes(self._buffer[start:end]))
        envelopes = find_envelopes(fields) if fields else []
        if not fields or (not envelopes and not self._synchronised):
            return FrameStatus.INVALID, [], 0
        return FrameStatus.COMPLETE, envelopes, self._base + end
