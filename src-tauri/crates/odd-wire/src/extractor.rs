//! Extraction of game messages from one direction of a reassembled TCP stream.
//!
//! While the stream is in sync, frames are read one after the other (long ones included). When it is not
//! (capture started mid-stream, lost bytes), a bounded search finds the next frame start. See `resync`.

use crate::envelope::{Envelope, envelopes_of};
use crate::frame::{Frame, frame_at};
use crate::resync::Budget;

/// Longest frame accepted while the stream is in sync (a mount listing is about 85 KB).
pub const MAX_FRAME_BYTES: usize = 1_048_576;
/// Most bytes kept; older bytes are dropped.
pub const MAX_BUFFER_BYTES: usize = 4 * MAX_FRAME_BYTES;
const COMPACT_THRESHOLD_BYTES: usize = 65_536;

/// Extracts the envelopes of a byte stream, fed in chunks of any size.
#[derive(Debug, Default)]
pub struct EnvelopeExtractor {
    pub(crate) buffer: Vec<u8>,
    /// Offset of the first byte not consumed yet.
    pub(crate) start: usize,
    /// Offset from which the next type URL is searched while out of sync.
    pub(crate) scan_from: usize,
    pub(crate) synchronised: bool,
}

impl EnvelopeExtractor {
    /// An extractor with nothing buffered, out of sync.
    pub fn new() -> Self {
        Self::default()
    }

    /// Forgets everything buffered and the synchronisation state.
    pub fn reset(&mut self) {
        *self = Self::default();
    }

    /// Bytes currently held.
    pub fn buffered_bytes(&self) -> usize {
        self.buffer.len() - self.start
    }

    /// Adds stream bytes and returns the envelopes of every frame that is now complete.
    pub fn feed(&mut self, data: &[u8]) -> Vec<Envelope> {
        self.buffer.extend_from_slice(data);
        self.drop_oldest_if_full();
        let mut budget = Budget::for_feed(data.len());
        let mut found = Vec::new();
        while self.advance(&mut found, &mut budget) {}
        self.compact();
        found
    }

    fn advance(&mut self, found: &mut Vec<Envelope>, budget: &mut Budget) -> bool {
        if self.synchronised {
            self.advance_synchronised(found)
        } else {
            self.advance_resync(found, budget)
        }
    }

    fn advance_synchronised(&mut self, found: &mut Vec<Envelope>) -> bool {
        match frame_at(&self.buffer[self.start..], MAX_FRAME_BYTES) {
            Frame::Incomplete => false,
            Frame::Invalid => self.lose_sync(),
            Frame::Complete { header, total } => {
                let body = &self.buffer[self.start + header..self.start + total];
                match envelopes_of(body) {
                    Some(envelopes) => {
                        found.extend(envelopes);
                        self.start += total;
                        true
                    }
                    None => self.lose_sync(),
                }
            }
        }
    }

    /// Gives up the current frame start: skips one byte and looks for a new start.
    fn lose_sync(&mut self) -> bool {
        self.start += 1;
        self.scan_from = self.start;
        self.synchronised = false;
        true
    }

    fn drop_oldest_if_full(&mut self) {
        if self.buffered_bytes() > MAX_BUFFER_BYTES {
            self.start = self.buffer.len() - MAX_BUFFER_BYTES;
            self.scan_from = self.start;
            self.synchronised = false;
        }
    }

    fn compact(&mut self) {
        if self.start >= COMPACT_THRESHOLD_BYTES || self.start == self.buffer.len() {
            self.buffer.drain(..self.start);
            self.scan_from = self.scan_from.saturating_sub(self.start);
            self.start = 0;
        }
    }
}
