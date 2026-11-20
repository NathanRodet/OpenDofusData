//! Extraction of messages from a byte stream: normal flow, resynchronisation, limits and hostile streams.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::time::{Duration, Instant};

use odd_wire::testkit::{any_message, envelope_frame, frame, outer_message};
use odd_wire::{Envelope, EnvelopeExtractor, MAX_BUFFER_BYTES, MAX_FRAME_BYTES, TYPE_URL_PREFIX};
use proptest::prelude::*;

fn envelope(name: &str, payload: &[u8]) -> Envelope {
    Envelope {
        type_name: name.to_owned(),
        payload: payload.to_vec(),
    }
}

fn noise(seed: u64, length: usize) -> Vec<u8> {
    let mut state = seed | 1;
    (0..length)
        .map(|_| {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            (state >> 24) as u8
        })
        .collect()
}

#[test]
fn a_single_envelope_is_extracted() {
    let mut extractor = EnvelopeExtractor::new();
    assert_eq!(
        extractor.feed(&envelope_frame("kcy", b"\x08\x01")),
        vec![envelope("kcy", b"\x08\x01")]
    );
}

#[test]
fn an_envelope_split_across_two_feeds_comes_out_once_complete() {
    let data = envelope_frame("kcy", b"hello");
    let mut extractor = EnvelopeExtractor::new();
    assert!(extractor.feed(&data[..5]).is_empty());
    assert_eq!(extractor.feed(&data[5..]), vec![envelope("kcy", b"hello")]);
}

#[test]
fn two_envelopes_in_one_feed_keep_their_order() {
    let data = [envelope_frame("one", b"1"), envelope_frame("two", b"2")].concat();
    assert_eq!(
        EnvelopeExtractor::new().feed(&data),
        vec![envelope("one", b"1"), envelope("two", b"2")]
    );
}

#[test]
fn a_stream_started_in_the_middle_skips_the_garbage() {
    let data = [noise(1234, 40), envelope_frame("abc", b"xyz")].concat();
    assert_eq!(EnvelopeExtractor::new().feed(&data), vec![envelope("abc", b"xyz")]);
}

#[test]
fn reset_drops_the_partial_buffer() {
    let data = envelope_frame("kcy", b"hello");
    let mut extractor = EnvelopeExtractor::new();
    extractor.feed(&data[..5]);
    extractor.reset();
    assert!(extractor.feed(&data[5..]).is_empty());
    assert_eq!(extractor.feed(&data), vec![envelope("kcy", b"hello")]);
}

#[test]
fn a_frame_over_the_limit_is_dropped_and_its_neighbours_recovered() {
    let huge = frame(&outer_message(&[any_message("huge", &vec![0; MAX_FRAME_BYTES + 1])]));
    let data = [envelope_frame("one", b"1"), huge, envelope_frame("two", b"2")].concat();
    assert_eq!(
        EnvelopeExtractor::new().feed(&data),
        vec![envelope("one", b"1"), envelope("two", b"2")]
    );
}

#[test]
fn a_long_message_is_read_once_the_stream_is_synchronised() {
    let payload: Vec<u8> = (0..=255u8).cycle().take(100_000).collect();
    let data = [
        envelope_frame("one", b"1"),
        envelope_frame("jzs", &payload),
        envelope_frame("two", b"2"),
    ]
    .concat();
    let found = EnvelopeExtractor::new().feed(&data);
    assert_eq!(
        found,
        vec![envelope("one", b"1"), envelope("jzs", &payload), envelope("two", b"2")]
    );
}

#[test]
fn a_long_message_met_before_any_synchronisation_is_skipped_but_the_next_ones_are_read() {
    let payload: Vec<u8> = (0..=255u8).cycle().take(300_000).collect();
    let data = [envelope_frame("jzs", &payload), envelope_frame("two", b"2")].concat();
    assert_eq!(EnvelopeExtractor::new().feed(&data), vec![envelope("two", b"2")]);
}

#[test]
fn the_buffer_never_grows_past_its_limit_on_garbage() {
    let mut extractor = EnvelopeExtractor::new();
    for round in 0..40 {
        extractor.feed(&noise(round + 7, 200_000));
        assert!(extractor.buffered_bytes() <= MAX_BUFFER_BYTES);
    }
}

#[test]
fn the_stream_recovers_after_garbage_fills_the_buffer() {
    let mut extractor = EnvelopeExtractor::new();
    assert!(extractor.feed(&envelope_frame("one", b"1")).len() == 1);
    extractor.feed(&noise(99, MAX_BUFFER_BYTES * 2));
    assert_eq!(
        extractor.feed(&envelope_frame("two", b"2")),
        vec![envelope("two", b"2")]
    );
}

fn within(limit: Duration, stream: &[u8]) -> Duration {
    let started = Instant::now();
    let mut extractor = EnvelopeExtractor::new();
    for chunk in stream.chunks(1460) {
        extractor.feed(chunk);
    }
    let elapsed = started.elapsed();
    assert!(elapsed < limit, "took {elapsed:?}, the limit is {limit:?}");
    elapsed
}

#[test]
fn random_noise_is_processed_in_bounded_time() {
    within(Duration::from_secs(10), &noise(5, 3_000_000));
}

#[test]
fn long_length_prefixes_repeated_are_processed_in_bounded_time() {
    let unit = [&[0x80, 0x80, 0x0f][..], TYPE_URL_PREFIX, &[0x08, 0x01][..]].concat();
    let stream: Vec<u8> = unit.iter().copied().cycle().take(3_000_000).collect();
    within(Duration::from_secs(10), &stream);
}

#[test]
fn a_repeating_pattern_of_cheap_frames_is_processed_in_bounded_time() {
    let stream: Vec<u8> = [0x80u8, 0x80, 0x0f].iter().copied().cycle().take(1_000_000).collect();
    within(Duration::from_secs(10), &stream);
}

proptest! {
    #[test]
    fn any_split_gives_the_same_envelopes(chunk in 1usize..400, names in proptest::collection::vec("[a-z]{1,6}", 1..6)) {
        let frames: Vec<Vec<u8>> = names.iter().map(|name| envelope_frame(name, name.as_bytes())).collect();
        let data = frames.concat();
        let expected: Vec<Envelope> = names.iter().map(|name| envelope(name, name.as_bytes())).collect();
        let mut extractor = EnvelopeExtractor::new();
        let mut found = Vec::new();
        for part in data.chunks(chunk) {
            found.extend(extractor.feed(part));
        }
        prop_assert_eq!(found, expected);
    }
}
