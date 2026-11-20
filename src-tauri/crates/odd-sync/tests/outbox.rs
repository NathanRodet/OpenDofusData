//! The queue of objects waiting to be sent: only the freshest object of each slot is kept.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Event, HdvLots, Offer, Payload, SCHEMA_VERSION};
use odd_sync::{MAX_PENDING_EVENTS, Outbox, PushOutcome};

fn lots(event_id: &str, server: &str, item: i64, at: &str, price: i64) -> Event {
    let offer = Offer {
        offer_id: 1,
        price,
        effects: vec![],
        unmapped: vec![],
    };
    Event {
        schema: SCHEMA_VERSION,
        event_id: event_id.to_owned(),
        observed_at: at.to_owned(),
        game_server: server.to_owned(),
        client_version: "2.4.0".to_owned(),
        payload: Payload::HdvLots(HdvLots::unique(item, Some(11), vec![offer])),
    }
}

fn ids(events: &[Event]) -> Vec<&str> {
    events.iter().map(|event| event.event_id.as_str()).collect()
}

#[test]
fn a_newer_object_replaces_the_waiting_one_of_the_same_slot() {
    let mut outbox = Outbox::new();
    assert_eq!(
        outbox.push(lots("old", "S", 1, "2026-11-19T10:00:00Z", 100)),
        PushOutcome::Queued
    );
    assert_eq!(
        outbox.push(lots("new", "S", 1, "2026-11-19T10:05:00Z", 120)),
        PushOutcome::Replaced
    );
    assert_eq!(outbox.len(), 1);
    assert_eq!(ids(&outbox.take_batch(10)), ["new"]);
}

#[test]
fn an_older_or_equal_object_is_dropped() {
    let mut outbox = Outbox::new();
    outbox.push(lots("kept", "S", 1, "2026-11-19T10:00:00Z", 100));
    assert_eq!(
        outbox.push(lots("older", "S", 1, "2026-11-19T09:00:00Z", 90)),
        PushOutcome::Stale
    );
    assert_eq!(
        outbox.push(lots("same", "S", 1, "2026-11-19T10:00:00Z", 95)),
        PushOutcome::Stale
    );
    assert_eq!(ids(&outbox.take_batch(10)), ["kept"]);
}

#[test]
fn other_items_and_other_servers_are_other_slots() {
    let mut outbox = Outbox::new();
    outbox.push(lots("a", "S", 1, "2026-11-19T10:00:00Z", 1));
    outbox.push(lots("b", "S", 2, "2026-11-19T10:00:00Z", 1));
    outbox.push(lots("c", "T", 1, "2026-11-19T10:00:00Z", 1));
    assert_eq!(outbox.len(), 3);
}

#[test]
fn objects_leave_oldest_slot_first_and_batches_are_bounded() {
    let mut outbox = Outbox::new();
    for item in 1..=5 {
        outbox.push(lots(&format!("e{item}"), "S", item, "2026-11-19T10:00:00Z", 1));
    }
    assert_eq!(ids(&outbox.take_batch(2)), ["e1", "e2"]);
    assert_eq!(outbox.len(), 3);
    assert_eq!(ids(&outbox.take_batch(100)), ["e3", "e4", "e5"]);
    assert!(outbox.is_empty());
}

#[test]
fn an_object_whose_send_failed_goes_back_unless_a_newer_one_waits() {
    let mut outbox = Outbox::new();
    outbox.push(lots("a", "S", 1, "2026-11-19T10:00:00Z", 1));
    outbox.push(lots("b", "S", 2, "2026-11-19T10:00:00Z", 1));
    let batch = outbox.take_batch(10);
    outbox.push(lots("a-newer", "S", 1, "2026-11-19T10:10:00Z", 2));
    outbox.put_back(batch);
    let mut waiting = ids(&outbox.take_batch(10))
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<_>>();
    waiting.sort();
    assert_eq!(
        waiting,
        ["a-newer", "b"],
        "the failed older object of slot 1 is not put back"
    );
}

#[test]
fn the_queue_is_bounded_and_forgets_the_oldest_slots() {
    let mut outbox = Outbox::new();
    let extra = 3;
    for item in 0..i64::try_from(MAX_PENDING_EVENTS + extra).unwrap() {
        outbox.push(lots(&format!("e{item}"), "S", item, "2026-11-19T10:00:00Z", 1));
    }
    assert_eq!(outbox.len(), MAX_PENDING_EVENTS);
    assert_eq!(outbox.dropped(), extra);
    assert_eq!(ids(&outbox.take_batch(1)), [format!("e{extra}")]);
}

#[test]
fn an_object_with_an_unreadable_date_is_refused() {
    let mut outbox = Outbox::new();
    assert_eq!(outbox.push(lots("bad", "S", 1, "yesterday", 1)), PushOutcome::Invalid);
    assert!(outbox.is_empty());
}

#[test]
fn a_failed_object_that_is_fresher_than_the_waiting_one_replaces_it() {
    let mut outbox = Outbox::new();
    outbox.push(lots("fresh", "S", 1, "2026-11-19T10:00:00Z", 1));
    let batch = outbox.take_batch(10);
    outbox.push(lots("older", "S", 1, "2026-11-19T09:00:00Z", 1));
    outbox.put_back(batch);
    assert_eq!(outbox.len(), 1);
    assert_eq!(ids(&outbox.take_batch(10)), ["fresh"]);
}
