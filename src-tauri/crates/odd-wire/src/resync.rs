//! Finding a frame start when the stream is out of sync, with a bounded amount of work.
//!
//! A frame holds a type URL near its start, so the search looks for the URL and tries the few
//! positions just before it. Each try costs its frame length; a budget per `feed` call caps the total.

use crate::envelope::{Envelope, TYPE_URL_PREFIX, envelopes_of};
use crate::extractor::EnvelopeExtractor;
use crate::frame::{Frame, frame_at};

/// Longest frame accepted while looking for a frame start.
pub const RESYNC_MAX_FRAME_BYTES: usize = 65_536;
/// How far before a type URL a frame can start.
const RESYNC_LOOKBACK_BYTES: usize = 1024;
const BUDGET_BASE_BYTES: usize = 2 * RESYNC_MAX_FRAME_BYTES;
const BUDGET_PER_FED_BYTE: usize = 2;
const COST_OF_AN_INVALID_TRY: usize = 1;

/// Work allowed for one `feed` call.
pub(crate) struct Budget {
    remaining: usize,
}

impl Budget {
    pub(crate) fn for_feed(fed: usize) -> Self {
        Self {
            remaining: BUDGET_BASE_BYTES + BUDGET_PER_FED_BYTE * fed,
        }
    }

    fn spend(&mut self, cost: usize) {
        self.remaining = self.remaining.saturating_sub(cost);
    }

    fn exhausted(&self) -> bool {
        self.remaining == 0
    }
}

enum Outcome {
    Synchronised,
    WaitForMoreData,
    NextUrl,
    OutOfBudget,
}

fn find_url(window: &[u8]) -> Option<usize> {
    let first = *TYPE_URL_PREFIX.first()?;
    let mut offset = 0;
    while let Some(index) = window[offset..].iter().position(|byte| *byte == first) {
        let at = offset + index;
        if window[at..].starts_with(TYPE_URL_PREFIX) {
            return Some(at);
        }
        offset = at + 1;
    }
    None
}

impl EnvelopeExtractor {
    /// One step of the search. Returns whether more work can be done right now.
    pub(crate) fn advance_resync(&mut self, found: &mut Vec<Envelope>, budget: &mut Budget) -> bool {
        let from = self.scan_from.max(self.start);
        let Some(url) = find_url(&self.buffer[from..]).map(|index| from + index) else {
            self.park();
            return false;
        };
        match self.try_starts_before(url, found, budget) {
            Outcome::Synchronised => true,
            Outcome::NextUrl => {
                self.scan_from = url + 1;
                true
            }
            Outcome::OutOfBudget => {
                self.scan_from = url + 1;
                false
            }
            Outcome::WaitForMoreData => false,
        }
    }

    /// No type URL in the buffer: keeps only the tail that could still hold a frame start.
    fn park(&mut self) {
        let len = self.buffer.len();
        self.start = self
            .start
            .max(len.saturating_sub(RESYNC_LOOKBACK_BYTES + TYPE_URL_PREFIX.len()));
        self.scan_from = len.saturating_sub(TYPE_URL_PREFIX.len() - 1).max(self.start);
    }

    /// Tries every start just before the type URL. A complete valid frame wins; otherwise the first start
    /// whose frame is not fully buffered yet is kept, so the search waits for its bytes.
    fn try_starts_before(&mut self, url: usize, found: &mut Vec<Envelope>, budget: &mut Budget) -> Outcome {
        let first = url.saturating_sub(RESYNC_LOOKBACK_BYTES).max(self.start);
        let mut waiting_for = None;
        for candidate in first..url {
            if budget.exhausted() {
                return Outcome::OutOfBudget;
            }
            match frame_at(&self.buffer[candidate..], RESYNC_MAX_FRAME_BYTES) {
                Frame::Incomplete => waiting_for = waiting_for.or(Some(candidate)),
                Frame::Invalid => budget.spend(COST_OF_AN_INVALID_TRY),
                Frame::Complete { header, total } => {
                    budget.spend(total);
                    if self.accept(candidate, header, total, found) {
                        return Outcome::Synchronised;
                    }
                }
            }
        }
        match waiting_for {
            Some(candidate) => {
                self.start = candidate;
                self.scan_from = url;
                Outcome::WaitForMoreData
            }
            None => Outcome::NextUrl,
        }
    }

    fn accept(&mut self, candidate: usize, header: usize, total: usize, found: &mut Vec<Envelope>) -> bool {
        match envelopes_of(&self.buffer[candidate + header..candidate + total]) {
            Some(envelopes) if !envelopes.is_empty() => {
                found.extend(envelopes);
                self.start = candidate + total;
                self.synchronised = true;
                true
            }
            _ => false,
        }
    }
}
