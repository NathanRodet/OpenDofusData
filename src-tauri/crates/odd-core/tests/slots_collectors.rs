//! A map holds one tax collector: the slot of a sighting or of a dialog is the map, whatever the cell.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Event, Payload, PercepteurSeen, PercepteurSheet, SCHEMA_VERSION, Slot, slot_of};
use time::macros::datetime;

fn event(payload: Payload) -> Event {
    Event {
        schema: SCHEMA_VERSION,
        event_id: "e".to_owned(),
        observed_at: "2026-11-27T20:00:00Z".to_owned(),
        game_server: "Kourial".to_owned(),
        client_version: "2.4.3".to_owned(),
        payload,
    }
}

fn seen(cell: i64) -> Payload {
    Payload::PercepteurSeen(PercepteurSeen {
        map_id: 240_386_053,
        sub_area_id: 1119,
        cell,
        direction: None,
        alliance: String::new(),
        tag: String::new(),
        name_ids: vec![],
        emblem: vec![],
    })
}

fn sheet(cell: i64) -> Payload {
    Payload::PercepteurSheet(PercepteurSheet {
        map_id: 240_386_053,
        cell,
        alliance: String::new(),
        tag: String::new(),
        alliance_collectors: 1,
        pod_capacity: 2000,
        prospecting: 300,
        pods: 0,
        value: 0,
    })
}

#[test]
fn the_cell_does_not_change_the_slot_of_a_sighting_or_of_a_dialog() {
    let at = datetime!(2026-11-27 20:00 UTC);
    assert_eq!(slot_of(&event(seen(317)), at), slot_of(&event(seen(12)), at));
    assert_eq!(slot_of(&event(sheet(317)), at), slot_of(&event(sheet(12)), at));
    let slot = slot_of(&event(seen(317)), at);
    assert_eq!(
        (slot.kind(), slot.subject()),
        ("percepteur_seen", "240386053".to_owned())
    );
    assert_eq!(slot_of(&event(sheet(1)), at).kind(), "percepteur_sheet");
    assert!(matches!(slot, Slot::PercepteurSeen { .. }));
}
