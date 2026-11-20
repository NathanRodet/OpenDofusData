//! Helpers shared by the tests of the agent: the reference captures cut into frames of a TCP connection.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]
#![allow(dead_code)]

use std::path::Path;

use etherparse::PacketBuilder;
use odd_agent::Pipeline;
use odd_core::Payload;
use odd_decode::{Decoder, Direction};
use odd_wire::Envelope;
use odd_wire::testkit::{envelope_frame, field_bytes, field_fixed32, field_message, field_packed, field_varint};
use serde_json::Value;
use time::OffsetDateTime;
use time::macros::datetime;

pub const GAME_PORT: u16 = 5555;
pub const NOW: OffsetDateTime = datetime!(2026-11-19 19:30:32 UTC);
pub const CLIENT: [u8; 4] = [192, 168, 1, 20];
pub const SERVER: [u8; 4] = [51, 77, 10, 3];
pub const FIXTURES: [&str; 10] = [
    "brisage-focus",
    "brisage-jet",
    "brisage-lot",
    "brisage-multi",
    "hdv-equipement",
    "hdv-graphique",
    "hdv-monture",
    "hdv-recherche",
    "hdv-ressource",
    "hdv-sans-offre",
];

pub type Record = (Direction, Envelope);

pub fn encode_fields(nodes: &[Value]) -> Vec<u8> {
    nodes.iter().flat_map(encode_node).collect()
}

pub fn encode_node(node: &Value) -> Vec<u8> {
    let number = u32::try_from(node["number"].as_u64().unwrap()).unwrap();
    match node["wire_type"].as_u64().unwrap() {
        0 => field_varint(number, node["value"].as_u64().unwrap()),
        5 => field_fixed32(number, u32::try_from(node["value"].as_u64().unwrap()).unwrap()),
        _ => encode_bytes(number, node),
    }
}

pub fn encode_bytes(number: u32, node: &Value) -> Vec<u8> {
    if let Some(children) = node["fields"].as_array() {
        return field_message(number, &[encode_fields(children)]);
    }
    if let Some(packed) = node["packed"].as_array() {
        let values: Vec<u64> = packed.iter().map(|value| value.as_u64().unwrap()).collect();
        return field_packed(number, &values);
    }
    field_bytes(
        number,
        &vec![0; usize::try_from(node["length"].as_u64().unwrap_or(0)).unwrap()],
    )
}

pub fn records(name: &str) -> Vec<Record> {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../odd-decode/tests/fixtures")
        .join(format!("{name}.jsonl"));
    std::fs::read_to_string(path)
        .unwrap()
        .lines()
        .map(|line| {
            let record: Value = serde_json::from_str(line).unwrap();
            let direction = if record["direction"] == "client_to_server" {
                Direction::ToServer
            } else {
                Direction::ToClient
            };
            let envelope = Envelope {
                type_name: record["type"].as_str().unwrap().to_owned(),
                payload: encode_fields(record["fields"].as_array().unwrap()),
            };
            (direction, envelope)
        })
        .collect()
}

pub fn expected(records: &[Record]) -> Vec<Payload> {
    let mut decoder = Decoder::new();
    records
        .iter()
        .flat_map(|(direction, envelope)| decoder.handle(*direction, envelope, NOW).payloads)
        .collect()
}

/// A TCP segment before it is wrapped in a frame.
#[derive(Clone)]
pub struct Segment {
    pub to_server: bool,
    pub client_port: u16,
    pub seq: u32,
    pub bytes: Vec<u8>,
    pub syn: bool,
    pub rst: bool,
}

impl Segment {
    pub fn frame(&self) -> Vec<u8> {
        let (source, destination) = if self.to_server {
            (CLIENT, SERVER)
        } else {
            (SERVER, CLIENT)
        };
        let (source_port, destination_port) = if self.to_server {
            (self.client_port, GAME_PORT)
        } else {
            (GAME_PORT, self.client_port)
        };
        let mut builder = PacketBuilder::ethernet2([1; 6], [2; 6])
            .ipv4(source, destination, 64)
            .tcp(source_port, destination_port, self.seq, 4096);
        if self.syn {
            builder = builder.syn();
        }
        if self.rst {
            builder = builder.rst();
        }
        let mut out = Vec::new();
        builder.write(&mut out, &self.bytes).unwrap();
        out
    }
}

/// A small message in each direction, as every real connection starts with: it puts the stream in sync before
/// the large messages of the captures (a mount listing is 85 KB, more than a stream out of sync accepts).
pub fn greeting() -> Vec<Record> {
    let hello = |direction| {
        (
            direction,
            Envelope {
                type_name: "hello".to_owned(),
                payload: field_varint(1, 1),
            },
        )
    };
    vec![hello(Direction::ToServer), hello(Direction::ToClient)]
}

/// Cuts every message into segments of at most `mss` bytes, in the order the messages happened.
pub fn segments(records: &[Record], mss: usize, client_port: u16) -> Vec<Segment> {
    let records: Vec<Record> = greeting().into_iter().chain(records.iter().cloned()).collect();
    let (mut client_seq, mut server_seq) = (1000_u32, 900_000_u32);
    let opening = |to_server, seq| Segment {
        to_server,
        client_port,
        seq,
        bytes: Vec::new(),
        syn: true,
        rst: false,
    };
    let mut out = vec![opening(true, client_seq - 1), opening(false, server_seq - 1)];
    for (direction, envelope) in &records {
        let to_server = *direction == Direction::ToServer;
        let bytes = envelope_frame(&envelope.type_name, &envelope.payload);
        for chunk in bytes.chunks(mss) {
            let seq = if to_server { &mut client_seq } else { &mut server_seq };
            out.push(Segment {
                to_server,
                client_port,
                seq: *seq,
                bytes: chunk.to_vec(),
                syn: false,
                rst: false,
            });
            *seq = seq.wrapping_add(u32::try_from(chunk.len()).unwrap());
        }
    }
    out
}

pub fn run(pipeline: &mut Pipeline, segments: &[Segment]) -> Vec<Payload> {
    run_named("", pipeline, segments)
}

pub fn run_named(label: &str, pipeline: &mut Pipeline, segments: &[Segment]) -> Vec<Payload> {
    let mut out = Vec::new();
    for segment in segments {
        let decoded = pipeline.handle_frame(&segment.frame(), NOW);
        assert!(decoded.issues.is_empty(), "{label}: {:?}", decoded.issues);
        out.extend(decoded.payloads);
    }
    out
}
