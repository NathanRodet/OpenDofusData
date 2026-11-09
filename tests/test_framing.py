"""Tests for envelope extraction from a reassembled TCP stream."""

import random

from dofus_prices.framing import (
    MAX_BUFFER_BYTES,
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
    assert len(extractor._buffer) <= MAX_BUFFER_BYTES


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


def test_random_garbage_never_raises() -> None:
    generator = random.Random(GARBAGE_SEED)
    extractor = EnvelopeExtractor()
    for _ in range(GARBAGE_CHUNKS):
        chunk = generator.randbytes(generator.randrange(1, 300))
        assert isinstance(extractor.feed(chunk), list)
