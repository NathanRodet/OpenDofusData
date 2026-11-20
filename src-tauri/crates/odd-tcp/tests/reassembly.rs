//! Putting TCP segments back in order: reordering, retransmissions, overlaps, losses, closing.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::net::{IpAddr, Ipv4Addr, SocketAddr};

use odd_tcp::{FlowId, FlowKey, MAX_FLOWS, MAX_PENDING_BYTES, Reassembler, Side, StreamEvent, TcpSegment};
use proptest::prelude::*;

fn key(client_port: u16) -> FlowKey {
    let client = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(10, 0, 0, 2)), client_port);
    let server = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(10, 0, 0, 9)), 5555);
    FlowKey::new(client, server)
}

fn data(client_port: u16, from: Side, seq: u32, payload: &[u8]) -> TcpSegment {
    TcpSegment {
        key: key(client_port),
        from,
        seq,
        payload: payload.to_vec(),
        syn: false,
        fin: false,
        rst: false,
    }
}

fn syn(client_port: u16, from: Side, seq: u32) -> TcpSegment {
    TcpSegment {
        syn: true,
        ..data(client_port, from, seq, &[])
    }
}

fn bytes_of(events: &[StreamEvent], from: Side) -> Vec<u8> {
    let mut out = Vec::new();
    for event in events {
        if let StreamEvent::Data { from: side, bytes, .. } = event
            && *side == from
        {
            out.extend_from_slice(bytes);
        }
    }
    out
}

fn push_all(reassembler: &mut Reassembler, segments: Vec<TcpSegment>) -> Vec<StreamEvent> {
    segments
        .into_iter()
        .flat_map(|segment| reassembler.push(segment))
        .collect()
}

#[test]
fn in_order_data_is_forwarded_at_once() {
    let mut reassembler = Reassembler::new();
    let events = push_all(
        &mut reassembler,
        vec![data(1, Side::Client, 100, b"abc"), data(1, Side::Client, 103, b"def")],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"abcdef");
}

#[test]
fn a_segment_that_arrives_early_waits_for_the_missing_one() {
    let mut reassembler = Reassembler::new();
    let first = reassembler.push(data(1, Side::Server, 100, b"abc"));
    let early = reassembler.push(data(1, Side::Server, 106, b"ghi"));
    assert!(early.is_empty(), "the gap blocks delivery");
    let filled = reassembler.push(data(1, Side::Server, 103, b"def"));
    assert_eq!(bytes_of(&first, Side::Server), b"abc");
    assert_eq!(bytes_of(&filled, Side::Server), b"defghi");
}

#[test]
fn a_retransmitted_segment_is_delivered_once() {
    let mut reassembler = Reassembler::new();
    let events = push_all(
        &mut reassembler,
        vec![
            data(1, Side::Client, 100, b"abc"),
            data(1, Side::Client, 100, b"abc"),
            data(1, Side::Client, 103, b"d"),
        ],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"abcd");
}

#[test]
fn a_partly_overlapping_segment_only_gives_its_new_bytes() {
    let mut reassembler = Reassembler::new();
    let events = push_all(
        &mut reassembler,
        vec![data(1, Side::Client, 100, b"abcd"), data(1, Side::Client, 102, b"cdef")],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"abcdef");
}

#[test]
fn sequence_numbers_wrap_around() {
    let mut reassembler = Reassembler::new();
    let start = u32::MAX - 2;
    let events = push_all(
        &mut reassembler,
        vec![
            data(1, Side::Client, start, b"abc"),
            data(1, Side::Client, start.wrapping_add(3), b"def"),
        ],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"abcdef");
}

#[test]
fn a_syn_uses_one_sequence_number() {
    let mut reassembler = Reassembler::new();
    let events = push_all(
        &mut reassembler,
        vec![syn(1, Side::Client, 500), data(1, Side::Client, 501, b"hi")],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"hi");
}

#[test]
fn a_capture_that_starts_mid_stream_starts_at_the_first_segment() {
    let mut reassembler = Reassembler::new();
    let events = reassembler.push(data(1, Side::Server, 9_000_000, b"middle"));
    assert_eq!(bytes_of(&events, Side::Server), b"middle");
}

#[test]
fn the_two_directions_are_independent() {
    let mut reassembler = Reassembler::new();
    let events = push_all(
        &mut reassembler,
        vec![
            data(1, Side::Client, 10, b"up"),
            data(1, Side::Server, 90_000, b"down"),
            data(1, Side::Client, 12, b"2"),
        ],
    );
    assert_eq!(bytes_of(&events, Side::Client), b"up2");
    assert_eq!(bytes_of(&events, Side::Server), b"down");
}

#[test]
fn a_lost_segment_is_declared_once_too_much_waits() {
    let mut reassembler = Reassembler::new();
    reassembler.push(data(1, Side::Server, 0, b"start"));
    let lost_after = 5 + 10;
    let big = vec![7_u8; MAX_PENDING_BYTES + 1];
    let events = reassembler.push(data(1, Side::Server, lost_after, &big));
    assert!(
        events.iter().any(|event| matches!(event, StreamEvent::Gap { .. })),
        "{events:?}"
    );
    assert_eq!(bytes_of(&events, Side::Server), big, "delivery goes on after the gap");
}

#[test]
fn a_fin_closes_the_flow_and_a_later_segment_starts_a_new_one() {
    let mut reassembler = Reassembler::new();
    let opened = reassembler.push(data(1, Side::Client, 1, b"a"));
    let flow = flow_of(&opened);
    let closing = TcpSegment {
        fin: true,
        ..data(1, Side::Client, 2, &[])
    };
    let closed = reassembler.push(closing);
    assert!(closed.contains(&StreamEvent::Closed { flow }));
    let reopened = reassembler.push(data(1, Side::Client, 500, b"b"));
    assert_ne!(flow_of(&reopened), flow);
}

#[test]
fn a_reset_closes_the_flow() {
    let mut reassembler = Reassembler::new();
    let flow = flow_of(&reassembler.push(data(1, Side::Server, 1, b"a")));
    let reset = TcpSegment {
        rst: true,
        ..data(1, Side::Server, 2, &[])
    };
    assert!(reassembler.push(reset).contains(&StreamEvent::Closed { flow }));
}

#[test]
fn separate_connections_have_separate_flows() {
    let mut reassembler = Reassembler::new();
    let first = flow_of(&reassembler.push(data(1, Side::Client, 1, b"a")));
    let second = flow_of(&reassembler.push(data(2, Side::Client, 1, b"a")));
    assert_ne!(first, second);
}

#[test]
fn the_oldest_flow_is_closed_when_there_are_too_many() {
    let mut reassembler = Reassembler::new();
    let oldest = flow_of(&reassembler.push(data(1, Side::Client, 1, b"a")));
    let mut closed = Vec::new();
    for port in 2..=u16::try_from(MAX_FLOWS).unwrap() + 1 {
        closed.extend(reassembler.push(data(port, Side::Client, 1, b"a")));
    }
    assert!(closed.contains(&StreamEvent::Closed { flow: oldest }));
}

fn flow_of(events: &[StreamEvent]) -> FlowId {
    events
        .iter()
        .find_map(|event| match event {
            StreamEvent::Data { flow, .. } => Some(*flow),
            _ => None,
        })
        .unwrap()
}

proptest! {
    #[test]
    fn any_order_and_any_duplicates_rebuild_the_stream(
        stream in proptest::collection::vec(any::<u8>(), 1..2000),
        chunk_sizes in proptest::collection::vec(1_usize..200, 1..40),
        start in any::<u32>(),
        shuffle_seed in any::<u64>(),
    ) {
        let mut segments = Vec::new();
        let (mut offset, mut sizes) = (0_usize, chunk_sizes.iter().cycle());
        while offset < stream.len() {
            let size = (*sizes.next().unwrap()).min(stream.len() - offset);
            let seq = start.wrapping_add(1).wrapping_add(u32::try_from(offset).unwrap());
            segments.push(data(1, Side::Client, seq, &stream[offset..offset + size]));
            offset += size;
        }
        let duplicates: Vec<TcpSegment> = segments.iter().step_by(3).cloned().collect();
        segments.extend(duplicates);
        let mut state = shuffle_seed | 1;
        for index in (1..segments.len()).rev() {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            segments.swap(index, usize::try_from(state % (index as u64 + 1)).unwrap());
        }
        let mut reassembler = Reassembler::new();
        let mut events = reassembler.push(syn(1, Side::Client, start));
        events.extend(push_all(&mut reassembler, segments));
        prop_assert_eq!(bytes_of(&events, Side::Client), stream);
    }
}
