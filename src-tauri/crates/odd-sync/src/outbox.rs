//! The objects waiting to be sent. The collector keeps only the freshest object of each slot, so the client does
//! the same: a newer object replaces the waiting one, and an older one is not worth sending.

use std::collections::{HashMap, VecDeque};

use odd_core::{Event, Slot, slot_of};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

/// Slots waiting at most. Beyond it the slots waiting longest are forgotten: the collector prefers fresh data.
pub const MAX_PENDING_EVENTS: usize = 2000;

/// What `push` did with an object.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PushOutcome {
    /// A new slot is waiting.
    Queued,
    /// It replaced an older object of the same slot.
    Replaced,
    /// A fresher or equally fresh object of the slot is already waiting: nothing to send.
    Stale,
    /// Its observation date cannot be read: it is refused.
    Invalid,
}

/// The queue of objects to send.
#[derive(Debug, Default)]
pub struct Outbox {
    order: VecDeque<Slot>,
    waiting: HashMap<Slot, (OffsetDateTime, Event)>,
    dropped: usize,
}

impl Outbox {
    /// An empty queue.
    pub fn new() -> Self {
        Self::default()
    }

    /// Number of slots waiting.
    pub fn len(&self) -> usize {
        self.waiting.len()
    }

    /// Whether nothing is waiting.
    pub fn is_empty(&self) -> bool {
        self.waiting.is_empty()
    }

    /// How many objects were forgotten because the queue was full.
    pub fn dropped(&self) -> usize {
        self.dropped
    }

    /// Queues an object, unless one at least as fresh already waits for the same slot.
    pub fn push(&mut self, event: Event) -> PushOutcome {
        let Ok(at) = OffsetDateTime::parse(&event.observed_at, &Rfc3339) else {
            return PushOutcome::Invalid;
        };
        let slot = slot_of(&event, at);
        match self.waiting.get(&slot) {
            Some((held, _)) if *held >= at => return PushOutcome::Stale,
            Some(_) => {
                self.waiting.insert(slot, (at, event));
                return PushOutcome::Replaced;
            }
            None => {}
        }
        self.order.push_back(slot.clone());
        self.waiting.insert(slot, (at, event));
        self.forget_overflow();
        PushOutcome::Queued
    }

    /// Takes up to `max` objects, the slots waiting longest first.
    pub fn take_batch(&mut self, max: usize) -> Vec<Event> {
        let mut batch = Vec::new();
        while batch.len() < max {
            let Some(slot) = self.order.pop_front() else {
                break;
            };
            if let Some((_, event)) = self.waiting.remove(&slot) {
                batch.push(event);
            }
        }
        batch
    }

    /// Puts back objects that could not be sent, unless a fresher object of the slot waits meanwhile.
    pub fn put_back(&mut self, events: Vec<Event>) {
        for event in events.into_iter().rev() {
            let Ok(at) = OffsetDateTime::parse(&event.observed_at, &Rfc3339) else {
                continue;
            };
            let slot = slot_of(&event, at);
            match self.waiting.get(&slot) {
                Some((held, _)) if *held >= at => {}
                Some(_) => {
                    self.waiting.insert(slot, (at, event));
                }
                None => {
                    self.order.push_front(slot.clone());
                    self.waiting.insert(slot, (at, event));
                }
            }
        }
        self.forget_overflow();
    }

    fn forget_overflow(&mut self) {
        while self.waiting.len() > MAX_PENDING_EVENTS {
            let Some(slot) = self.order.pop_front() else {
                break;
            };
            if self.waiting.remove(&slot).is_some() {
                self.dropped += 1;
            }
        }
    }
}
