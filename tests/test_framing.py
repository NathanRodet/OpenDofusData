"""Tests for envelope extraction from a reassembled TCP stream."""

import random

import pytest

from opendofusdata import framing
from opendofusdata.framing import (
    MAX_BUFFER_BYTES,
    MAX_FRAME_BYTES,
    TYPE_URL_PREFIX,
    Envelope,
    EnvelopeExtractor,
)

VARINT_PAYLOAD_MASK = 0x7F
VARINT_CONTINUATION_BIT = 0x80
VARINT_PAYLOAD_BITS = 7
LENGTH_DELIMITED_WIRE_TYPE = 2
WIRE_TYPE_BITS = 3
GARBAGE_SEED = 1234
GARBAGE_BYTES = 1_000_000
GARBAGE_CHUNKS = 40
MIXED_FRAME_COUNT = 24
MIXED_PAYLOAD_SIZES = (0, 5, 300, 4000, 30000)
LINEAR_GARBAGE_BYTES = 200_000
MAX_CALLS_PER_BYTE = 4


def encode_varint(value: int) -> bytes:
    encoded = bytearray()
    while value > VARINT_PAYLOAD_MASK:
        encoded.append((value & VARINT_PAYLOAD_MASK) | VARINT_CONTINUATION_BIT)
        value >>= VARINT_PAYLOAD_BITS
    encoded.append(value)
    return bytes(encoded)


def length_delimited_field(number: int, content: bytes) -> bytes:
    tag = (number << WIRE_TYPE_BITS) | LENGTH_DELIMITED_WIRE_TYPE
    return encode_varint(tag) + encode_varint(len(content)) + content


def any_message(type_name: str, payload: bytes | None) -> bytes:
    url = TYPE_URL_PREFIX + type_name.encode()
    message = length_delimited_field(1, url)
    if payload is not None:
        message += length_delimited_field(2, payload)
    return message


def outer_message(*children: bytes) -> bytes:
    return b"".join(length_delimited_field(3, child) for child in children)


def frame(body: bytes) -> bytes:
    return encode_varint(len(body)) + body


def envelope_frame(type_name: str, payload: bytes | None) -> bytes:
    return frame(outer_message(any_message(type_name, payload)))


def test_single_envelope_extracted() -> None:
    extractor = EnvelopeExtractor()
    assert extractor.feed(envelope_frame("kcy", b"\x08\x01")) == [
        Envelope("kcy", b"\x08\x01")
    ]


def test_envelope_split_across_two_feeds() -> None:
    data = envelope_frame("kcy", b"hello")
    extractor = EnvelopeExtractor()
    assert extractor.feed(data[:5]) == []
    assert extractor.feed(data[5:]) == [Envelope("kcy", b"hello")]


def test_stream_started_mid_message_skips_garbage() -> None:
    garbage = random.Random(GARBAGE_SEED).randbytes(40)
    extractor = EnvelopeExtractor()
    result = extractor.feed(garbage + envelope_frame("abc", b"xyz"))
    assert result == [Envelope("abc", b"xyz")]


def test_two_envelopes_in_one_feed() -> None:
    data = envelope_frame("one", b"1") + envelope_frame("two", b"2")
    assert EnvelopeExtractor().feed(data) == [
        Envelope("one", b"1"),
        Envelope("two", b"2"),
    ]


def test_reset_drops_partial_buffer() -> None:
    data = envelope_frame("kcy", b"hello")
    extractor = EnvelopeExtractor()
    extractor.feed(data[:5])
    extractor.reset()
    assert extractor.feed(data[5:]) == []
    assert extractor.feed(data) == [Envelope("kcy", b"hello")]


def test_buffer_is_bounded() -> None:
    extractor = EnvelopeExtractor()
    garbage = random.Random(GARBAGE_SEED).randbytes(GARBAGE_BYTES)
    extractor.feed(garbage)
    assert extractor.buffered_bytes <= MAX_BUFFER_BYTES


def test_envelope_nested_two_levels_deep() -> None:
    nested = outer_message(outer_message(any_message("deep", b"p")))
    assert EnvelopeExtractor().feed(frame(nested)) == [Envelope("deep", b"p")]


def test_frame_without_envelope_between_envelope_frames() -> None:
    plain = frame(length_delimited_field(5, b"no envelope here"))
    data = envelope_frame("one", b"1") + plain + envelope_frame("two", b"2")
    assert EnvelopeExtractor().feed(data) == [
        Envelope("one", b"1"),
        Envelope("two", b"2"),
    ]


def test_any_without_payload_field_gives_empty_payload() -> None:
    assert EnvelopeExtractor().feed(envelope_frame("empty", None)) == [
        Envelope("empty", b"")
    ]


def test_several_envelopes_in_one_frame() -> None:
    body = outer_message(any_message("a", b"1"), any_message("b", b"2"))
    assert EnvelopeExtractor().feed(frame(body)) == [
        Envelope("a", b"1"),
        Envelope("b", b"2"),
    ]


def test_resynchronises_after_corrupt_frame() -> None:
    extractor = EnvelopeExtractor()
    extractor.feed(envelope_frame("one", b"1"))
    result = extractor.feed(b"\xff\xff\xff\xff" + envelope_frame("two", b"2"))
    assert result == [Envelope("two", b"2")]


def test_random_garbage_never_raises_nor_invents_envelopes() -> None:
    generator = random.Random(GARBAGE_SEED)
    extractor = EnvelopeExtractor()
    for _ in range(GARBAGE_CHUNKS):
        chunk = generator.randbytes(generator.randrange(1, 300))
        assert extractor.feed(chunk) == []


def build_stream(seed: int) -> tuple[bytes, list[tuple[int, list[Envelope]]]]:
    """Build a mixed stream; return it with (frame start offset, envelopes) pairs."""
    generator = random.Random(seed)
    stream = b""
    frames: list[tuple[int, list[Envelope]]] = []
    for index in range(MIXED_FRAME_COUNT):
        size = generator.choice(MIXED_PAYLOAD_SIZES)
        payload = generator.randbytes(size)
        if index % 3 == 1:
            body, found = length_delimited_field(5, payload or b"x"), []
        else:
            found = [Envelope(f"msg{index}", payload)]
            body = outer_message(any_message(f"msg{index}", payload))
        frames.append((len(stream), found))
        stream += frame(body)
    return stream, frames


def feed_in_chunks(data: bytes, chunk_size: int) -> list[Envelope]:
    extractor = EnvelopeExtractor()
    found: list[Envelope] = []
    for offset in range(0, len(data), chunk_size):
        found += extractor.feed(data[offset : offset + chunk_size])
    return found


@pytest.mark.parametrize("chunk_size", [7, 1460])
def test_mixed_stream_in_chunks_yields_all_envelopes_in_order(chunk_size: int) -> None:
    stream, frames = build_stream(GARBAGE_SEED)
    expected = [envelope for _, found in frames for envelope in found]
    assert feed_in_chunks(stream, chunk_size) == expected


@pytest.mark.parametrize("chunk_size", [7, 1460])
@pytest.mark.parametrize("cut_fraction", [0.1, 0.37, 0.5, 0.83])
def test_stream_cut_mid_frame_recovers_following_envelopes(
    chunk_size: int, cut_fraction: float
) -> None:
    stream, frames = build_stream(GARBAGE_SEED)
    cut = int(len(stream) * cut_fraction) + 1
    after_cut = [(start, found) for start, found in frames if start >= cut and found]
    expected = [envelope for _, found in after_cut for envelope in found]
    result = feed_in_chunks(stream[cut:], chunk_size)
    assert result == expected


def test_oversize_frame_is_dropped_and_neighbours_recovered() -> None:
    huge = frame(outer_message(any_message("huge", bytes(MAX_FRAME_BYTES + 1))))
    data = envelope_frame("one", b"1") + huge + envelope_frame("two", b"2")
    assert EnvelopeExtractor().feed(data) == [Envelope("one", b"1"), Envelope("two", b"2")]


def test_overflow_while_synchronised_recovers_on_later_frames() -> None:
    extractor = EnvelopeExtractor()
    assert extractor.feed(envelope_frame("one", b"1")) == [Envelope("one", b"1")]
    extractor.feed(random.Random(GARBAGE_SEED).randbytes(MAX_BUFFER_BYTES * 2))
    assert extractor.buffered_bytes <= MAX_BUFFER_BYTES
    assert extractor.feed(envelope_frame("two", b"2")) == [Envelope("two", b"2")]


@pytest.mark.parametrize("chunk_size", [7, 1460])
def test_scanning_work_is_linear_in_bytes_received(
    monkeypatch: pytest.MonkeyPatch, chunk_size: int
) -> None:
    calls = 0
    original = framing.read_varint

    def counting_read_varint(data: bytes, offset: int) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        return original(data, offset)

    monkeypatch.setattr(framing, "read_varint", counting_read_varint)
    garbage = random.Random(GARBAGE_SEED).randbytes(LINEAR_GARBAGE_BYTES)
    assert feed_in_chunks(garbage, chunk_size) == []
    assert calls <= MAX_CALLS_PER_BYTE * LINEAR_GARBAGE_BYTES
