//! The dev mode capture: the structure of a message, never its text.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_agent::{Observation, Recorded, Recorder, describe_message};
use odd_decode::Direction;
use odd_wire::Envelope;
use odd_wire::testkit::field_packed;
use odd_wire::testkit::{field_bytes, field_message, field_varint};
use serde_json::Value;
use time::macros::datetime;

fn observation(payload: Vec<u8>) -> Observation {
    Observation {
        direction: Direction::ToClient,
        envelope: Envelope {
            type_name: "abc".to_owned(),
            payload,
        },
        at: datetime!(2026-11-27 10:15:30 UTC),
    }
}

fn parsed(observation: &Observation) -> Value {
    serde_json::from_str(&describe_message(observation, false).unwrap()).unwrap()
}

#[test]
fn a_line_names_the_time_the_direction_the_type_and_the_size() {
    let line = parsed(&observation(field_varint(1, 96_134)));
    assert_eq!(line["time"], "2026-11-27T10:15:30Z");
    assert_eq!(line["direction"], "server_to_client");
    assert_eq!(line["type"], "abc");
    assert_eq!(line["size"], 4);
}

#[test]
fn integers_and_nested_messages_keep_their_numbers() {
    let inner = [field_varint(2, 96_134), field_varint(3, 7)].concat();
    let line = parsed(&observation(field_message(1, &[inner])));
    let outer = &line["fields"][0];
    assert_eq!(
        (outer["number"].as_u64(), outer["wire_type"].as_u64()),
        (Some(1), Some(2))
    );
    assert_eq!(outer["fields"][0]["value"], 96_134);
    assert_eq!(outer["fields"][1]["number"], 3);
}

#[test]
fn text_is_never_written_only_its_length() {
    // "Meta Partage" is not a protobuf message: only its length is kept.
    let text = b"Meta Partage";
    let described = describe_message(&observation(field_bytes(4, text)), false).unwrap();
    assert!(!described.contains("Meta"));
    assert!(described.contains("\"length\":12"));
}

#[test]
fn the_recorder_writes_one_line_per_message_in_a_file_named_after_the_time() {
    let directory = std::env::temp_dir().join(format!("odd-capture-test-{}", std::process::id()));
    let mut recorder = Recorder::create(&directory, datetime!(2026-11-27 10:15:30 UTC), &[]).unwrap();
    assert!(recorder.path().ends_with("capture-2026-11-27-10-15-30.jsonl"));
    for number in [1, 2] {
        let outcome = recorder.record(&observation(field_varint(1, number))).unwrap();
        assert_eq!(outcome, Recorded::Written);
    }
    let text = std::fs::read_to_string(recorder.path()).unwrap();
    assert_eq!(text.lines().count(), 2);
    std::fs::remove_dir_all(directory).unwrap();
}

#[test]
fn a_detailed_type_also_gives_the_bytes_and_the_packed_numbers_of_opaque_fields() {
    let payload = [field_packed(2, &[96_134, 43_298, 7]), field_bytes(3, b"Meta")].concat();
    let line: Value = serde_json::from_str(&describe_message(&observation(payload), true).unwrap()).unwrap();
    let numbers = &line["fields"][0];
    assert_eq!(numbers["packed"], serde_json::json!([96_134, 43_298, 7]));
    assert!(numbers["hex"].as_str().unwrap().starts_with("86"), "{numbers}");
    assert_eq!(line["fields"][1]["hex"], "4d657461");
}

#[test]
fn the_recorder_details_only_the_types_it_was_given() {
    let directory = std::env::temp_dir().join(format!("odd-capture-detail-{}", std::process::id()));
    let mut recorder = Recorder::create(&directory, datetime!(2026-11-27 10:15:30 UTC), &["abc".to_owned()]).unwrap();
    recorder.record(&observation(field_bytes(3, b"Meta"))).unwrap();
    let mut other = observation(field_bytes(3, b"Meta"));
    other.envelope.type_name = "zzz".to_owned();
    recorder.record(&other).unwrap();
    let text = std::fs::read_to_string(recorder.path()).unwrap();
    let lines: Vec<&str> = text.lines().collect();
    assert!(lines[0].contains("4d657461"), "the listed type is detailed");
    assert!(!lines[1].contains("4d657461"), "the others never are");
    std::fs::remove_dir_all(directory).unwrap();
}
