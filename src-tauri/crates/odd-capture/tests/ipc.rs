//! The transport of captured frames between the worker and the agent: a length, then the frame.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::io::{Cursor, Read};

use odd_capture::{FrameReader, IpcError, MAX_FRAME_BYTES, encode_frame};

/// A reader that gives one byte at a time, like a slow pipe.
struct Trickle(Cursor<Vec<u8>>);

impl Read for Trickle {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        let take = buffer.len().min(1);
        self.0.read(&mut buffer[..take])
    }
}

#[test]
fn frames_come_back_in_order() {
    let mut wire = Vec::new();
    for frame in [&b"first"[..], b"", b"third frame"] {
        wire.extend(encode_frame(frame));
    }
    let mut reader = FrameReader::new(Cursor::new(wire));
    assert_eq!(reader.next_frame().unwrap().unwrap(), b"first");
    assert_eq!(reader.next_frame().unwrap().unwrap(), b"");
    assert_eq!(reader.next_frame().unwrap().unwrap(), b"third frame");
    assert!(
        reader.next_frame().unwrap().is_none(),
        "a clean end of stream is not an error"
    );
}

#[test]
fn a_slow_pipe_gives_the_same_frames() {
    let wire = [encode_frame(&[7; 300]), encode_frame(b"x")].concat();
    let mut reader = FrameReader::new(Trickle(Cursor::new(wire)));
    assert_eq!(reader.next_frame().unwrap().unwrap(), vec![7; 300]);
    assert_eq!(reader.next_frame().unwrap().unwrap(), b"x");
}

#[test]
fn a_stream_cut_in_the_middle_of_a_frame_is_an_error() {
    let mut wire = encode_frame(b"complete");
    wire.truncate(wire.len() - 2);
    assert!(matches!(
        FrameReader::new(Cursor::new(wire)).next_frame(),
        Err(IpcError::Truncated)
    ));
    let only_half_a_length = vec![1, 0];
    assert!(matches!(
        FrameReader::new(Cursor::new(only_half_a_length)).next_frame(),
        Err(IpcError::Truncated)
    ));
}

#[test]
fn an_absurd_length_is_refused_before_anything_is_allocated() {
    let wire = u32::try_from(MAX_FRAME_BYTES + 1).unwrap().to_le_bytes().to_vec();
    assert!(matches!(
        FrameReader::new(Cursor::new(wire)).next_frame(),
        Err(IpcError::FrameTooLong { .. })
    ));
}

#[test]
fn the_largest_frame_is_accepted() {
    let wire = encode_frame(&vec![1; MAX_FRAME_BYTES]);
    assert_eq!(
        FrameReader::new(Cursor::new(wire)).next_frame().unwrap().unwrap().len(),
        MAX_FRAME_BYTES
    );
}
