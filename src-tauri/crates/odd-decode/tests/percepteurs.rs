//! The tax collectors window, shaped like the capture of 2026-11-27 (values and names are invented).
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Payload, Percepteur, Percepteurs};
use odd_decode::{Decoder, Direction, Issue};
use odd_wire::Envelope;
use odd_wire::testkit::{field_bytes, field_message, field_varint};
use time::macros::datetime;

fn negative(value: i64) -> u64 {
    u64::from_ne_bytes(value.to_ne_bytes())
}

struct Line {
    value: u64,
    x: i64,
    y: i64,
    sub_area: u64,
    alliance: &'static str,
    tag: &'static str,
    owner: &'static str,
}

fn encode(line: &Line) -> Vec<u8> {
    let value_box = field_message(
        1,
        &[field_message(2, &[field_varint(1, 623), field_varint(3, line.value)])],
    );
    let position = field_message(
        2,
        &[field_varint(1, negative(line.y)), field_varint(3, negative(line.x))],
    );
    let alliance = field_message(
        16,
        &[
            field_bytes(2, b"9e427b21-45be-4c3e-9c9a-bcc07fac"),
            field_bytes(4, line.tag.as_bytes()),
            field_bytes(6, line.alliance.as_bytes()),
        ],
    );
    [
        value_box,
        position,
        field_bytes(8, line.owner.as_bytes()),
        field_varint(9, line.sub_area),
        alliance,
    ]
    .concat()
}

fn answer(classic: &[Line], dungeon: &[Line]) -> Envelope {
    let parts: Vec<Vec<u8>> = classic
        .iter()
        .map(|line| field_bytes(1, &encode(line)))
        .chain(dungeon.iter().map(|line| field_bytes(2, &encode(line))))
        .collect();
    Envelope {
        type_name: "hht".to_owned(),
        payload: parts.concat(),
    }
}

fn first() -> Line {
    Line {
        value: 279_686,
        x: -21,
        y: 9,
        sub_area: 235,
        alliance: "FREE GHOST",
        tag: "FRGO",
        owner: "Exemple",
    }
}

fn decode(envelope: &Envelope) -> (Vec<Payload>, Vec<Issue>) {
    let decoded = Decoder::new().handle(Direction::ToClient, envelope, datetime!(2026-11-27 19:44:48 UTC));
    (decoded.payloads, decoded.issues)
}

#[test]
fn both_tabs_give_one_object_with_every_field_of_a_line() {
    let other = Line {
        value: 1_560_389,
        x: 0,
        y: -70,
        sub_area: 624,
        alliance: "Perco Mubarak",
        tag: "RAZIA",
        owner: "Autre",
    };
    let (payloads, issues) = decode(&answer(&[first()], &[other]));
    assert!(issues.is_empty(), "{issues:?}");
    let expected = Percepteurs {
        classic: vec![Percepteur {
            alliance: "FREE GHOST".to_owned(),
            tag: "FRGO".to_owned(),
            owner: "Exemple".to_owned(),
            value: 279_686,
            sub_area_id: 235,
            x: -21,
            y: 9,
        }],
        dungeon: vec![Percepteur {
            alliance: "Perco Mubarak".to_owned(),
            tag: "RAZIA".to_owned(),
            owner: "Autre".to_owned(),
            value: 1_560_389,
            sub_area_id: 624,
            x: -0,
            y: -70,
        }],
    };
    assert_eq!(payloads, vec![Payload::Percepteurs(expected)]);
}

#[test]
fn an_answer_without_any_line_gives_nothing() {
    let (payloads, issues) = decode(&answer(&[], &[]));
    assert!(payloads.is_empty() && issues.is_empty());
}

#[test]
fn a_line_without_value_is_reported_and_the_others_are_kept() {
    let mut envelope = answer(&[first()], &[]);
    envelope.payload.extend(field_bytes(1, &field_bytes(8, b"Sans valeur")));
    let (payloads, issues) = decode(&envelope);
    assert_eq!(issues.len(), 1, "{issues:?}");
    let Payload::Percepteurs(window) = &payloads[0] else {
        panic!("a window was expected")
    };
    assert_eq!(window.classic.len(), 1);
}
