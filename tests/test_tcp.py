"""Tests for TCP stream reassembly."""

from dofus_prices.tcp import FlowTable, StreamReassembler, payload_length

SEQUENCE_MODULUS = 2**32
FLOW = ("10.0.0.1", 5555, "10.0.0.2", 50000)


def test_payload_length_ignores_ethernet_padding() -> None:
    assert payload_length(40, 20, 20) == 0


def test_payload_length_counts_data_bytes() -> None:
    assert payload_length(100, 20, 32) == 48


def test_in_order_segments_are_concatenated() -> None:
    reassembler = StreamReassembler()
    assert reassembler.feed(100, b"ab").data == b"ab"
    assert reassembler.feed(102, b"cd").data == b"cd"


def test_out_of_order_segment_is_held_until_gap_filled() -> None:
    reassembler = StreamReassembler()
    reassembler.feed(100, b"ab")
    assert reassembler.feed(104, b"ef").data == b""
    assert reassembler.feed(102, b"cd").data == b"cdef"


def test_retransmitted_segment_is_ignored() -> None:
    reassembler = StreamReassembler()
    reassembler.feed(100, b"ab")
    result = reassembler.feed(100, b"ab")
    assert result.data == b""
    assert not result.resynced


def test_partial_overlap_delivers_only_new_tail() -> None:
    reassembler = StreamReassembler()
    reassembler.feed(100, b"abc")
    assert reassembler.feed(101, b"bcde").data == b"de"


def test_sequence_wraparound() -> None:
    reassembler = StreamReassembler()
    assert reassembler.feed(SEQUENCE_MODULUS - 2, b"abcd").data == b"abcd"
    assert reassembler.feed(2, b"ef").data == b"ef"


def test_lost_packet_triggers_resync() -> None:
    reassembler = StreamReassembler(max_buffered_bytes=4)
    reassembler.feed(100, b"ab")
    assert reassembler.feed(110, b"xyz").data == b""
    result = reassembler.feed(113, b"uvw")
    assert result.resynced
    assert result.data == b"xyzuvw"
    follow_up = reassembler.feed(116, b"!")
    assert follow_up.data == b"!"
    assert not follow_up.resynced


def test_mid_connection_start_uses_first_segment_as_base() -> None:
    reassembler = StreamReassembler()
    assert reassembler.feed(987654321, b"hello").data == b"hello"
    assert reassembler.feed(987654326, b"!").data == b"!"


def test_flow_table_keeps_directions_separate() -> None:
    table = FlowTable()
    reverse = (FLOW[2], FLOW[3], FLOW[0], FLOW[1])
    assert table.feed(FLOW, 1, b"a", now=0.0).data == b"a"
    assert table.feed(reverse, 500, b"b", now=0.0).data == b"b"


def test_flow_table_purges_idle_flows() -> None:
    table = FlowTable(idle_seconds=10.0)
    table.feed(FLOW, 1, b"a", now=0.0)
    assert table.purge(now=5.0) == []
    assert table.purge(now=11.0) == [FLOW]
    assert table.feed(FLOW, 50, b"z", now=12.0).data == b"z"


def test_flow_table_activity_refreshes_idle_time() -> None:
    table = FlowTable(idle_seconds=10.0)
    table.feed(FLOW, 1, b"a", now=0.0)
    table.feed(FLOW, 2, b"b", now=8.0)
    assert table.purge(now=15.0) == []
