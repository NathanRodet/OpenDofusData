//! How long each kind of data is kept.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{
    DEFAULT_RETENTION, PERCEPTEURS_MET_RETENTION, PERCEPTEURS_RETENTION, Payload, PercepteurSeen, Percepteurs,
    retention_of_slot_kind,
};
use time::Duration;

#[test]
fn the_book_is_kept_four_hours_and_the_collectors_met_twelve() {
    assert_eq!(PERCEPTEURS_RETENTION, Duration::hours(4));
    assert_eq!(PERCEPTEURS_MET_RETENTION, Duration::hours(12));
    assert_eq!(retention_of_slot_kind("percepteurs"), Duration::hours(4));
    assert_eq!(retention_of_slot_kind("percepteur_seen"), Duration::hours(12));
    assert_eq!(retention_of_slot_kind("percepteur_sheet"), Duration::hours(12));
}

#[test]
fn everything_else_keeps_the_default_thirty_days() {
    assert_eq!(DEFAULT_RETENTION, Duration::days(30));
    for kind in ["hdv_lots", "hdv_stats", "hdv_category", "brisage", "unknown"] {
        assert_eq!(retention_of_slot_kind(kind), DEFAULT_RETENTION, "{kind}");
    }
}

#[test]
fn a_payload_and_its_stored_kind_agree_on_the_retention() {
    let book = Payload::Percepteurs(Percepteurs {
        classic: vec![],
        dungeon: vec![],
    });
    let seen = Payload::PercepteurSeen(PercepteurSeen {
        map_id: 1,
        sub_area_id: 1,
        cell: 1,
        direction: None,
        alliance: String::new(),
        tag: String::new(),
        name_ids: vec![],
        emblem: vec![],
    });
    assert_eq!(book.retention(), retention_of_slot_kind("percepteurs"));
    assert_eq!(seen.retention(), retention_of_slot_kind("percepteur_seen"));
}
