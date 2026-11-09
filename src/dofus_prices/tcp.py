"""TCP stream reassembly: pure logic, no capture or storage dependency."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEQUENCE_MODULUS = 2**32
HALF_SEQUENCE_SPACE = 2**31
DEFAULT_MAX_BUFFERED_BYTES = 65536
DEFAULT_IDLE_SECONDS = 300.0

FlowKey = tuple[str, int, str, int]


def payload_length(ip_total_length: int, ip_header_length: int, tcp_header_length: int) -> int:
    """Return the TCP data length from IP header fields, ignoring frame padding."""
    return max(0, ip_total_length - ip_header_length - tcp_header_length)


@dataclass
class Reassembled:
    """Bytes newly deliverable in order, and whether a gap was abandoned."""

    data: bytes
    resynced: bool


class StreamReassembler:
    """Reassembles one direction of a TCP stream into an ordered byte stream."""

    def __init__(self, max_buffered_bytes: int = DEFAULT_MAX_BUFFERED_BYTES) -> None:
        self._max_buffered_bytes = max_buffered_bytes
        self._base_sequence: int | None = None
        self._next_offset = 0
        self._pending: dict[int, bytes] = {}

    def feed(self, seq: int, payload: bytes) -> Reassembled:
        """Accept a segment and return the data that became deliverable."""
        if self._base_sequence is None:
            self._base_sequence = seq
        offset = self._to_offset(seq)
        if offset + len(payload) > self._next_offset:
            known = self._pending.get(offset, b"")
            self._pending[offset] = max(known, payload, key=len)
        delivered = self._drain()
        resynced = self._buffered_bytes() > self._max_buffered_bytes
        if resynced:
            delivered += self._abandon_gap()
        return Reassembled(data=delivered, resynced=resynced)

    def _to_offset(self, seq: int) -> int:
        """Unwrap a 32-bit sequence number to a 64-bit offset near the expected one."""
        assert self._base_sequence is not None
        expected = (self._base_sequence + self._next_offset) % SEQUENCE_MODULUS
        signed_distance = (seq - expected + HALF_SEQUENCE_SPACE) % SEQUENCE_MODULUS
        return self._next_offset + signed_distance - HALF_SEQUENCE_SPACE

    def _buffered_bytes(self) -> int:
        return sum(len(chunk) for chunk in self._pending.values())

    def _drain(self) -> bytes:
        """Deliver every pending chunk contiguous with the delivered stream."""
        delivered = bytearray()
        while self._pending and min(self._pending) <= self._next_offset:
            offset = min(self._pending)
            chunk = self._pending.pop(offset)
            delivered += chunk[self._next_offset - offset :]
            self._next_offset = max(self._next_offset, offset + len(chunk))
        return bytes(delivered)

    def _abandon_gap(self) -> bytes:
        """Skip the missing bytes and deliver the buffered data that follows."""
        self._next_offset = min(self._pending)
        logger.warning("TCP gap abandoned at stream offset %d", self._next_offset)
        return self._drain()


class FlowTable:
    """Keeps one reassembler per flow direction and expires idle flows."""

    def __init__(self, idle_seconds: float = DEFAULT_IDLE_SECONDS) -> None:
        self._idle_seconds = idle_seconds
        self._flows: dict[FlowKey, tuple[StreamReassembler, float]] = {}

    def feed(self, key: FlowKey, seq: int, payload: bytes, now: float) -> Reassembled:
        """Route a segment to its flow's reassembler and record the activity time."""
        reassembler = self._flows[key][0] if key in self._flows else StreamReassembler()
        self._flows[key] = (reassembler, now)
        return reassembler.feed(seq, payload)

    def purge(self, now: float) -> int:
        """Drop flows idle for longer than the limit; return how many were removed."""
        expired = [
            key for key, (_, last_seen) in self._flows.items()
            if now - last_seen > self._idle_seconds
        ]
        for key in expired:
            del self._flows[key]
        return len(expired)
