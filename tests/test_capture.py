"""Tests for the packet pipeline, using packets built in memory (no sniffing)."""

import pytest
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

from dofus_prices.capture import DOFUS_PORT, PacketPipeline, direction_of
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
