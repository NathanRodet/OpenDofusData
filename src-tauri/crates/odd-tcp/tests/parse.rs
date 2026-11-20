//! Reading TCP segments of the game connection out of raw Ethernet frames.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use etherparse::PacketBuilder;
use odd_tcp::{Side, parse_ethernet_frame};

const GAME_PORT: u16 = 5555;
const CLIENT_PORT: u16 = 50_321;
const MAC_A: [u8; 6] = [1, 2, 3, 4, 5, 6];
const MAC_B: [u8; 6] = [6, 5, 4, 3, 2, 1];
const CLIENT_V4: [u8; 4] = [192, 168, 1, 20];
const SERVER_V4: [u8; 4] = [51, 77, 10, 3];

fn frame_v4(from: ([u8; 4], u16), to: ([u8; 4], u16), seq: u32, payload: &[u8]) -> Vec<u8> {
    let builder = PacketBuilder::ethernet2(MAC_A, MAC_B)
        .ipv4(from.0, to.0, 64)
        .tcp(from.1, to.1, seq, 4096);
    let mut out = Vec::new();
    builder.write(&mut out, payload).unwrap();
    out
}

#[test]
fn a_frame_to_the_game_port_is_a_client_segment() {
    let frame = frame_v4((CLIENT_V4, CLIENT_PORT), (SERVER_V4, GAME_PORT), 1000, b"hello");
    let segment = parse_ethernet_frame(&frame, GAME_PORT).unwrap();
    assert_eq!(segment.from, Side::Client);
    assert_eq!(segment.seq, 1000);
    assert_eq!(segment.payload, b"hello");
    assert!(!segment.syn && !segment.fin && !segment.rst);
}

#[test]
fn a_frame_from_the_game_port_is_a_server_segment_of_the_same_flow() {
    let up = frame_v4((CLIENT_V4, CLIENT_PORT), (SERVER_V4, GAME_PORT), 1, b"a");
    let down = frame_v4((SERVER_V4, GAME_PORT), (CLIENT_V4, CLIENT_PORT), 9, b"b");
    let up = parse_ethernet_frame(&up, GAME_PORT).unwrap();
    let down = parse_ethernet_frame(&down, GAME_PORT).unwrap();
    assert_eq!(down.from, Side::Server);
    assert_eq!(up.key, down.key, "both directions belong to one flow");
}

#[test]
fn another_connection_gives_another_flow() {
    let first = frame_v4((CLIENT_V4, 50_000), (SERVER_V4, GAME_PORT), 1, b"a");
    let second = frame_v4((CLIENT_V4, 50_001), (SERVER_V4, GAME_PORT), 1, b"a");
    let first = parse_ethernet_frame(&first, GAME_PORT).unwrap();
    let second = parse_ethernet_frame(&second, GAME_PORT).unwrap();
    assert_ne!(first.key, second.key);
}

#[test]
fn tcp_flags_are_read() {
    let builder = PacketBuilder::ethernet2(MAC_A, MAC_B)
        .ipv4(CLIENT_V4, SERVER_V4, 64)
        .tcp(CLIENT_PORT, GAME_PORT, 7, 4096)
        .syn();
    let mut frame = Vec::new();
    builder.write(&mut frame, &[]).unwrap();
    let segment = parse_ethernet_frame(&frame, GAME_PORT).unwrap();
    assert!(segment.syn);
    assert!(segment.payload.is_empty());
}

#[test]
fn an_ipv6_frame_is_read() {
    let builder =
        PacketBuilder::ethernet2(MAC_A, MAC_B)
            .ipv6([1; 16], [2; 16], 64)
            .tcp(GAME_PORT, CLIENT_PORT, 55, 4096);
    let mut frame = Vec::new();
    builder.write(&mut frame, b"v6").unwrap();
    let segment = parse_ethernet_frame(&frame, GAME_PORT).unwrap();
    assert_eq!(
        (segment.from, segment.seq, segment.payload.as_slice()),
        (Side::Server, 55, &b"v6"[..])
    );
}

#[test]
fn other_ports_are_ignored() {
    let frame = frame_v4((CLIENT_V4, 40_000), (SERVER_V4, 443), 1, b"tls");
    assert!(parse_ethernet_frame(&frame, GAME_PORT).is_none());
}

#[test]
fn udp_is_ignored() {
    let builder = PacketBuilder::ethernet2(MAC_A, MAC_B)
        .ipv4(CLIENT_V4, SERVER_V4, 64)
        .udp(CLIENT_PORT, GAME_PORT);
    let mut frame = Vec::new();
    builder.write(&mut frame, b"udp").unwrap();
    assert!(parse_ethernet_frame(&frame, GAME_PORT).is_none());
}

#[test]
fn garbage_and_truncated_frames_are_ignored() {
    assert!(parse_ethernet_frame(&[], GAME_PORT).is_none());
    assert!(parse_ethernet_frame(&[0xFF; 7], GAME_PORT).is_none());
    let frame = frame_v4((CLIENT_V4, CLIENT_PORT), (SERVER_V4, GAME_PORT), 1, b"payload");
    assert!(parse_ethernet_frame(&frame[..20], GAME_PORT).is_none());
}

#[test]
fn a_flow_key_never_shows_the_addresses_when_printed() {
    let frame = frame_v4((CLIENT_V4, CLIENT_PORT), (SERVER_V4, GAME_PORT), 1, b"a");
    let segment = parse_ethernet_frame(&frame, GAME_PORT).unwrap();
    let printed = format!("{:?} {:?}", segment.key, segment);
    assert!(!printed.contains("192.168") && !printed.contains("51.77"), "{printed}");
}
