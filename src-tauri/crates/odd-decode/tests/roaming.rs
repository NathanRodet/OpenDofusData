//! The tax collectors met on a map, shaped like the capture of 2026-11-27 (ids and names are invented).
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Payload, PercepteurSeen, PercepteurSheet};
use odd_decode::{Decoder, Direction, Issue};
use odd_wire::Envelope;
use odd_wire::testkit::{field_bytes, field_message, field_varint};
use time::macros::datetime;

const MAP: u64 = 240_386_053;
const ENTITY: i64 = -20_006;

fn negative(value: i64) -> u64 {
    u64::from_ne_bytes(value.to_ne_bytes())
}

fn alliance() -> Vec<u8> {
    field_message(
        1,
        &[
            field_bytes(4, b"RAZIA"),
            field_bytes(6, b"Perco Mubarak"),
            field_message(3, &[field_varint(1, 16_233_022), field_varint(2, 8)]),
        ],
    )
}

fn collector_actor(entity: i64, cell: u64) -> Vec<u8> {
    let data = field_message(2, &[alliance(), field_varint(3, 185), field_varint(5, 11)]);
    let body = field_message(3, &[field_message(1, &[field_message(7, &[data])])]);
    let position = field_message(2, &[field_varint(3, cell), field_varint(4, 1)]);
    field_message(3, &[field_varint(1, negative(entity)), position, body])
}

fn player_actor() -> Vec<u8> {
    let position = field_message(2, &[field_varint(3, 100), field_varint(4, 3)]);
    field_message(3, &[field_varint(1, 7_006_650_723), position])
}

fn envelope(type_name: &str, parts: &[Vec<u8>]) -> Envelope {
    Envelope {
        type_name: type_name.to_owned(),
        payload: parts.concat(),
    }
}

fn map_entry(actors: Vec<Vec<u8>>) -> Envelope {
    let mut parts = actors;
    parts.extend([field_varint(10, MAP), field_varint(12, 1119)]);
    envelope("jnj", &parts)
}

fn opened(entity: i64) -> Envelope {
    envelope("ilx", &[field_varint(3, MAP), field_varint(5, negative(entity))])
}

fn sheet() -> Envelope {
    let alliance = field_message(2, &[field_bytes(4, b"RAZIA"), field_bytes(6, b"Perco Mubarak")]);
    envelope(
        "iku",
        &[
            field_varint(1, 49),
            alliance,
            field_varint(3, 2000),
            field_varint(4, 300),
            field_varint(5, 927),
            field_varint(6, 502_397),
        ],
    )
}

fn feed(decoder: &mut Decoder, envelope: &Envelope) -> (Vec<Payload>, Vec<Issue>) {
    let decoded = decoder.handle(Direction::ToClient, envelope, datetime!(2026-11-27 20:21:38 UTC));
    (decoded.payloads, decoded.issues)
}

#[test]
fn entering_a_map_gives_one_sighting_per_collector_and_ignores_other_actors() {
    let (payloads, issues) = feed(
        &mut Decoder::new(),
        &map_entry(vec![player_actor(), collector_actor(ENTITY, 317)]),
    );
    assert!(issues.is_empty(), "{issues:?}");
    let [Payload::PercepteurSeen(seen)] = payloads.as_slice() else {
        panic!("one sighting expected: {payloads:?}")
    };
    let expected = PercepteurSeen {
        map_id: 240_386_053,
        sub_area_id: 1119,
        cell: 317,
        direction: Some(1),
        alliance: "Perco Mubarak".to_owned(),
        tag: "RAZIA".to_owned(),
        name_ids: vec![185, 11],
        emblem: seen.emblem.clone(),
    };
    assert_eq!(seen, &expected);
    assert_eq!(seen.emblem.len(), 2, "the emblem fields are kept as received");
}

#[test]
fn a_map_without_collector_gives_nothing() {
    let (payloads, issues) = feed(&mut Decoder::new(), &map_entry(vec![player_actor()]));
    assert!(payloads.is_empty() && issues.is_empty());
}

#[test]
fn the_dialog_is_placed_on_the_map_by_the_entity_that_was_opened() {
    let mut decoder = Decoder::new();
    feed(&mut decoder, &map_entry(vec![collector_actor(ENTITY, 317)]));
    feed(&mut decoder, &opened(ENTITY));
    let (payloads, issues) = feed(&mut decoder, &sheet());
    assert!(issues.is_empty(), "{issues:?}");
    let expected = PercepteurSheet {
        map_id: 240_386_053,
        cell: 317,
        alliance: "Perco Mubarak".to_owned(),
        tag: "RAZIA".to_owned(),
        alliance_collectors: 49,
        pod_capacity: 2000,
        prospecting: 300,
        pods: 927,
        value: 502_397,
    };
    assert_eq!(payloads, vec![Payload::PercepteurSheet(expected)]);
}

#[test]
fn a_dialog_of_an_entity_not_seen_on_the_map_is_reported() {
    let mut decoder = Decoder::new();
    feed(&mut decoder, &map_entry(vec![collector_actor(ENTITY, 317)]));
    feed(&mut decoder, &opened(-1));
    let (payloads, issues) = feed(&mut decoder, &sheet());
    assert!(payloads.is_empty());
    assert_eq!(issues.len(), 1);
}

#[test]
fn a_dialog_without_an_opening_gives_nothing() {
    let (payloads, issues) = feed(&mut Decoder::new(), &sheet());
    assert!(payloads.is_empty() && issues.is_empty());
}
