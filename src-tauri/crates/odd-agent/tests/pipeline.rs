//! The whole path from raw Ethernet frames to decoded objects, on the real captures of the reference sessions,
//! cut into TCP segments of any size, reordered, duplicated and damaged.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

mod common;

use common::*;
use odd_agent::Pipeline;

#[test]
fn a_replayed_session_gives_the_objects_of_the_decoder_whatever_the_segment_size() {
    for name in FIXTURES {
        let records = records(name);
        for mss in [1460, 40, 7] {
            let got = run_named(name, &mut Pipeline::new(GAME_PORT), &segments(&records, mss, 50_000));
            assert_eq!(got, expected(&records), "{name} with segments of {mss} bytes");
        }
    }
}

#[test]
fn reordered_and_duplicated_segments_give_the_same_objects() {
    for name in FIXTURES {
        let records = records(name);
        let mut damaged = segments(&records, 9, 50_000);
        for pair in damaged
            .chunks_mut(2)
            .filter(|pair| pair.len() == 2 && pair[0].to_server == pair[1].to_server)
        {
            pair.swap(0, 1);
        }
        let mut with_retransmissions = Vec::new();
        for (index, segment) in damaged.iter().enumerate() {
            with_retransmissions.push(segment.clone());
            if index % 4 == 0 {
                with_retransmissions.push(segment.clone());
            }
        }
        let damaged = with_retransmissions;
        assert_eq!(
            run_named(name, &mut Pipeline::new(GAME_PORT), &damaged),
            expected(&records),
            "{name}"
        );
    }
}

#[test]
fn a_new_connection_decodes_after_a_connection_that_lost_a_segment() {
    let records = records("hdv-ressource");
    let mut broken = segments(&records, 9, 50_000);
    let lost = broken.iter().position(|segment| !segment.to_server).unwrap() + 1;
    broken.remove(lost);
    let reset = Segment {
        to_server: true,
        client_port: 50_000,
        seq: 99_999,
        bytes: Vec::new(),
        syn: false,
        rst: true,
    };
    let mut pipeline = Pipeline::new(GAME_PORT);
    run(&mut pipeline, &broken);
    run(&mut pipeline, &[reset]);
    let got = run(&mut pipeline, &segments(&records, 9, 50_001));
    assert_eq!(got, expected(&records));
}

#[test]
fn a_capture_that_starts_in_the_middle_of_a_message_recovers_on_the_next_one() {
    let records = records("hdv-ressource");
    let doubled: Vec<Record> = records.iter().chain(records.iter()).cloned().collect();
    let mut cut = segments(&doubled, 1460, 50_000);
    cut.retain(|segment| !segment.syn);
    for segment in cut.iter_mut().take(2) {
        segment.bytes.drain(..3);
        segment.seq = segment.seq.wrapping_add(3);
    }
    let got = run(&mut Pipeline::new(GAME_PORT), &cut);
    assert!(got.ends_with(&expected(&records)), "{got:?}");
}

#[test]
fn frames_that_are_not_the_game_are_ignored() {
    let mut pipeline = Pipeline::new(GAME_PORT);
    for frame in [vec![], vec![0xFF; 9], vec![0; 60]] {
        let decoded = pipeline.handle_frame(&frame, NOW);
        assert!(decoded.payloads.is_empty() && decoded.issues.is_empty());
    }
}

#[test]
fn recording_hands_over_every_message_seen_in_order_even_those_not_decoded() {
    let records = records("hdv-ressource");
    let mut pipeline = Pipeline::new(GAME_PORT);
    pipeline.set_recording(true);
    let mut seen = Vec::new();
    for segment in segments(&records, 1460, 50_000) {
        pipeline.handle_frame(&segment.frame(), NOW);
        seen.extend(pipeline.take_observed());
    }
    // The session starts with the greeting messages, which are seen too.
    let sent: Vec<(odd_decode::Direction, String)> = greeting()
        .iter()
        .chain(records.iter())
        .map(|(direction, envelope)| (*direction, envelope.type_name.clone()))
        .collect();
    let got: Vec<(odd_decode::Direction, String)> = seen
        .iter()
        .map(|each| (each.direction, each.envelope.type_name.clone()))
        .collect();
    assert_eq!(got, sent);
    assert!(pipeline.take_observed().is_empty(), "the messages are handed over once");
}

#[test]
fn nothing_is_kept_when_recording_is_off() {
    let records = records("hdv-ressource");
    let mut pipeline = Pipeline::new(GAME_PORT);
    run(&mut pipeline, &segments(&records, 1460, 50_000));
    assert!(pipeline.take_observed().is_empty());
}
