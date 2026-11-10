"""Tests for the packet pipeline, using packets built in memory (no sniffing)."""

import pytest
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

import logging

from dofus_prices.capture import DOFUS_PORT, CaptureAborted, PacketPipeline, direction_of
from dofus_prices.framing import TYPE_URL_PREFIX, Envelope

CLIENT = "10.0.0.2"
SERVER = "20.0.0.3"
CLIENT_PORT = 40000
ETHERNET_PADDING = b"\x00" * 6
DIRECTIONS = {"client_to_server": (CLIENT, CLIENT_PORT, SERVER, DOFUS_PORT)}


def varint(value: int) -> bytes:
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def field(number: int, content: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(content)) + content


def frame(type_name: str, payload: bytes) -> bytes:
    any_message = field(1, TYPE_URL_PREFIX + type_name.encode()) + field(2, payload)
    body = field(3, any_message)
    return varint(len(body)) + body


def segment(seq: int, payload: bytes, *, to_server: bool = True, padding: bytes = b"") -> IP:
    """Build a packet and re-parse its bytes so length fields are filled in."""
    src, dst = (CLIENT, SERVER) if to_server else (SERVER, CLIENT)
    ports = (CLIENT_PORT, DOFUS_PORT) if to_server else (DOFUS_PORT, CLIENT_PORT)
    tcp = TCP(sport=ports[0], dport=ports[1], seq=seq, flags="PA")
    packet = IP(src=src, dst=dst) / tcp / Raw(payload)
    return IP(bytes(packet) + padding)


@pytest.fixture
def delivered() -> list[tuple[Envelope, tuple]]:
    return []


@pytest.fixture
def pipeline(delivered) -> PacketPipeline:
    return PacketPipeline(lambda envelope, key: delivered.append((envelope, key)))


def test_data_segment_yields_envelope_with_flow_key(pipeline, delivered) -> None:
    pipeline.handle_packet(segment(1000, frame("Demo", b"abc")))
    assert delivered == [(Envelope("Demo", b"abc"), (CLIENT, CLIENT_PORT, SERVER, DOFUS_PORT))]


def test_envelope_split_across_segments_is_delivered_once(pipeline, delivered) -> None:
    data = frame("Demo", b"abcdef")
    pipeline.handle_packet(segment(1000, data[:10]))
    assert delivered == []
    pipeline.handle_packet(segment(1010, data[10:]))
    assert [envelope for envelope, _ in delivered] == [Envelope("Demo", b"abcdef")]


def test_ethernet_padding_after_empty_segment_is_ignored(pipeline, delivered) -> None:
    pipeline.handle_packet(segment(1000, b"", padding=ETHERNET_PADDING))
    pipeline.handle_packet(segment(1000, frame("Demo", b"x")))
    assert [envelope.type_name for envelope, _ in delivered] == ["Demo"]


def test_padding_after_data_is_not_added_to_stream(pipeline, delivered) -> None:
    data = frame("Demo", b"x")
    pipeline.handle_packet(segment(1000, data, padding=ETHERNET_PADDING))
    pipeline.handle_packet(segment(1000 + len(data), frame("Next", b"y")))
    assert [envelope.type_name for envelope, _ in delivered] == ["Demo", "Next"]


def test_empty_segment_does_not_set_the_base_sequence(pipeline, delivered) -> None:
    pipeline.handle_packet(segment(5, b""))
    pipeline.handle_packet(segment(1000, frame("Demo", b"x")))
    assert len(delivered) == 1


def test_directions_are_independent(pipeline, delivered) -> None:
    data = frame("Up", b"1")
    pipeline.handle_packet(segment(1000, data[:5]))
    pipeline.handle_packet(segment(7000, frame("Down", b"2"), to_server=False))
    pipeline.handle_packet(segment(1005, data[5:]))
    assert [envelope.type_name for envelope, _ in delivered] == ["Down", "Up"]


def test_non_tcp_packet_is_ignored(pipeline, delivered) -> None:
    pipeline.handle_packet(IP(src=CLIENT, dst=SERVER) / b"not tcp")
    pipeline.handle_packet(object())
    assert delivered == []


def test_callback_exception_does_not_escape(caplog) -> None:
    def failing(envelope, key) -> None:
        raise RuntimeError("boom")

    PacketPipeline(failing).handle_packet(segment(1000, frame("Demo", b"x")))
    assert "boom" in caplog.text


def test_direction_is_decided_by_the_server_port() -> None:
    assert direction_of((CLIENT, CLIENT_PORT, SERVER, DOFUS_PORT)) == "client_to_server"
    assert direction_of((SERVER, DOFUS_PORT, CLIENT, CLIENT_PORT)) == "server_to_client"


def offloaded(seq: int, payload: bytes) -> IP:
    packet = segment(seq, payload)
    packet["IP"].len = 0
    return packet


def test_zero_ip_length_falls_back_to_captured_payload_and_warns_once(
    pipeline, delivered, caplog
) -> None:
    caplog.set_level(logging.WARNING)
    first, second = frame("One", b"1"), frame("Two", b"2")
    pipeline.handle_packet(offloaded(1000, first))
    pipeline.handle_packet(offloaded(1000 + len(first), second))
    assert [envelope.type_name for envelope, _ in delivered] == ["One", "Two"]
    assert caplog.text.count("segmentation offload") == 1


def test_nonzero_ip_length_smaller_than_headers_is_dropped(pipeline, delivered) -> None:
    packet = segment(1000, frame("Demo", b"x"))
    packet["IP"].len = 10
    pipeline.handle_packet(packet)
    assert delivered == []


def test_capture_aborted_escapes_handle_packet() -> None:
    def aborting(envelope, key) -> None:
        raise CaptureAborted("disk full")

    with pytest.raises(CaptureAborted):
        PacketPipeline(aborting).handle_packet(segment(1000, frame("Demo", b"x")))


def test_failing_callback_does_not_discard_remaining_envelopes(caplog) -> None:
    seen: list[str] = []

    def flaky(envelope, key) -> None:
        seen.append(envelope.type_name)
        if envelope.type_name == "First":
            raise RuntimeError("boom")

    data = frame("First", b"1") + frame("Second", b"2")
    PacketPipeline(flaky).handle_packet(segment(1000, data))
    assert seen == ["First", "Second"]


def test_evicted_flow_starts_from_a_fresh_extractor(delivered) -> None:
    pipeline = PacketPipeline(lambda envelope, key: delivered.append((envelope, key)), max_flows=1)
    data = frame("Demo", b"abcdef")
    pipeline.handle_packet(segment(1000, data[:10]))
    other = IP(bytes(IP(src="10.0.0.9", dst=SERVER) / TCP(sport=41000, dport=DOFUS_PORT, seq=1)
                     / Raw(frame("Other", b"z"))))
    pipeline.handle_packet(other)
    pipeline.handle_packet(segment(1010, data[10:]))
    assert [envelope.type_name for envelope, _ in delivered] == ["Other"]
