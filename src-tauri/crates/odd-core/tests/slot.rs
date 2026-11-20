//! Which slot an event belongs to: the place where only the freshest event is kept.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Brisage, BrisageItem, Event, HdvLots, Payload, SCHEMA_VERSION, Slot, slot_of};
use time::macros::datetime;

fn event(server: &str, payload: Payload) -> Event {
    Event {
        schema: SCHEMA_VERSION,
        event_id: "e".to_owned(),
        observed_at: "2026-11-19T23:30:00Z".to_owned(),
        game_server: server.to_owned(),
        client_version: "2.4.0".to_owned(),
        payload,
    }
}

fn breaking(item: i64) -> Payload {
    let item = BrisageItem {
        id: item,
        quantity: 1,
        effects: vec![],
        unmapped: vec![],
    };
    Payload::Brisage(Brisage {
        item,
        focus_effect_id: None,
        coefficient: 1.0,
        coefficient_alt: None,
        runes: vec![],
    })
}

#[test]
fn lots_are_kept_per_server_and_item() {
    let lots = event("Kourial", Payload::HdvLots(HdvLots::unique(42, Some(11), vec![])));
    let slot = slot_of(&lots, datetime!(2026-11-19 23:30 UTC));
    assert_eq!(
        slot,
        Slot::HdvLots {
            server: "Kourial".to_owned(),
            item_id: 42
        }
    );
    assert_eq!(
        (slot.kind(), slot.server(), slot.subject().as_str()),
        ("hdv_lots", "Kourial", "42")
    );
}

#[test]
fn a_breaking_is_kept_per_item_and_utc_day() {
    let slot = slot_of(&event("Kourial", breaking(7)), datetime!(2026-11-19 23:30 UTC));
    assert_eq!(slot.kind(), "brisage");
    assert_eq!(slot.subject(), "7:2026-11-19");
    let next_day = slot_of(&event("Kourial", breaking(7)), datetime!(2026-11-20 00:00:01 UTC));
    assert_eq!(next_day.subject(), "7:2026-11-20");
}

#[test]
fn the_utc_day_ignores_the_offset_of_the_observation() {
    let late_evening_local = datetime!(2026-11-19 23:30 -05:00);
    assert_eq!(
        slot_of(&event("S", breaking(1)), late_evening_local).subject(),
        "1:2026-11-20"
    );
}

#[test]
fn stats_and_categories_have_their_own_kinds() {
    let stats = Slot::HdvStats {
        server: "S".to_owned(),
        item_id: 1,
    };
    let category = Slot::HdvCategory {
        server: "S".to_owned(),
        item_type_id: 1,
    };
    assert_ne!(stats.kind(), category.kind());
    assert_ne!(stats, category);
}
