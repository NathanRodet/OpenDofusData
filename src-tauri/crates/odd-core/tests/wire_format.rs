//! The JSON a collector receives: shapes of docs/json-schemas.md, round trips and size limits.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{
    Brisage, BrisageItem, Effect, Event, HdvCategory, HdvLots, HdvStats, Lot, MAX_EFFECTS, MAX_OFFERS_PER_ITEM,
    MAX_TEXT_CHARS, Offer, Payload, Period, Periods, Point, Points, Rune, SCHEMA_VERSION, Unmapped, Violation,
};
use proptest::prelude::*;
use serde_json::json;

fn envelope(payload: Payload) -> Event {
    Event {
        schema: SCHEMA_VERSION,
        event_id: "0194f0e2-7c1a-7b3e-9d51-3f6c2a8e41b0".into(),
        observed_at: "2026-11-19T19:40:38Z".into(),
        game_server: "Kourial".into(),
        client_version: "2.4.0".into(),
        payload,
    }
}

#[test]
fn a_resource_lots_event_has_the_documented_shape() {
    let lots = HdvLots::resource(
        310,
        Some(47),
        vec![Lot { size: 1, price: 22 }, Lot { size: 10, price: 272 }],
    );
    let value = serde_json::to_value(envelope(Payload::HdvLots(lots))).unwrap();
    assert_eq!(
        value,
        json!({
            "schema": 2, "event_id": "0194f0e2-7c1a-7b3e-9d51-3f6c2a8e41b0", "observed_at": "2026-11-19T19:40:38Z",
            "game_server": "Kourial", "client_version": "2.4.0", "kind": "hdv.lots",
            "data": { "item_id": 310, "item_type_id": 47, "lots": [{ "size": 1, "price": 22 }, { "size": 10, "price": 272 }] }
        })
    );
}

#[test]
fn unique_item_offers_keep_every_effect_form() {
    let mut named = Effect::text(3809, "Gronouille Rousse");
    named.unmapped.push(Unmapped::value("9.1", 331));
    let offer = Offer {
        offer_id: 61340,
        price: 5987,
        effects: vec![
            Effect::value(125, 3),
            Effect::range(100, 18, 22),
            Effect::gauge(2819, 0, 19),
            named,
        ],
        unmapped: vec![],
    };
    let event = envelope(Payload::HdvLots(HdvLots::unique(33063, Some(331), vec![offer])));
    let data = serde_json::to_value(event).unwrap()["data"].clone();
    assert_eq!(data["offers"][0]["effects"][0], json!({ "effect_id": 125, "value": 3 }));
    assert_eq!(
        data["offers"][0]["effects"][1],
        json!({ "effect_id": 100, "min": 18, "max": 22 })
    );
    assert_eq!(
        data["offers"][0]["effects"][2],
        json!({ "effect_id": 2819, "current": 0, "max": 19 })
    );
    assert_eq!(
        data["offers"][0]["effects"][3],
        json!({ "effect_id": 3809, "text": "Gronouille Rousse", "unmapped": [{ "path": "9.1", "value": 331 }] })
    );
}

#[test]
fn an_item_without_offer_is_an_empty_offer_list() {
    let event = envelope(Payload::HdvLots(HdvLots::unique(34548, Some(336), vec![])));
    let data = serde_json::to_value(event).unwrap()["data"].clone();
    assert_eq!(data, json!({ "item_id": 34548, "item_type_id": 336, "offers": [] }));
}

#[test]
fn stats_use_the_period_names_of_the_game() {
    let period = |sold, median, mean| Period { sold, median, mean };
    let stats = HdvStats {
        item_id: 310,
        last_purchase_at: Some("2026-11-19T18:09:59.606165396Z".into()),
        periods: Periods {
            h24: period(15163, 25, 21.4),
            d7: period(41751, 21, 18.0),
            d30: period(151417, 20, 451.55),
        },
        points: Points {
            hourly: vec![Point {
                at: "2026-11-18T19:43:58.843003778Z".into(),
                price: 9,
                quantity: 300,
            }],
            daily: vec![],
        },
    };
    let data = serde_json::to_value(envelope(Payload::HdvStats(stats))).unwrap()["data"].clone();
    assert_eq!(data["periods"]["24h"]["sold"], json!(15163));
    assert_eq!(data["periods"]["30d"]["mean"], json!(451.55));
    assert_eq!(data["points"]["hourly"][0]["quantity"], json!(300));
}

#[test]
fn a_category_lists_item_ids() {
    let value = serde_json::to_value(envelope(Payload::HdvCategory(HdvCategory {
        item_type_id: 336,
        item_ids: vec![34547, 34549],
    })))
    .unwrap();
    assert_eq!(value["kind"], json!("hdv.category"));
    assert_eq!(
        value["data"],
        json!({ "item_type_id": 336, "item_ids": [34547, 34549] })
    );
}

#[test]
fn a_breaking_without_focus_or_rune_leaves_those_keys_out() {
    let breaking = Brisage {
        item: BrisageItem {
            id: 6718,
            quantity: 1,
            effects: vec![Effect::value(125, 15)],
            unmapped: vec![],
        },
        focus_effect_id: None,
        coefficient: 0.5,
        coefficient_alt: Some(0.5),
        runes: vec![],
    };
    let data = serde_json::to_value(envelope(Payload::Brisage(breaking))).unwrap()["data"].clone();
    assert_eq!(data["coefficient"], json!(0.5));
    assert!(data.get("focus_effect_id").is_none());
    assert!(data.get("runes").is_none());
}

#[test]
fn a_breaking_with_focus_and_runes_keeps_them() {
    let breaking = Brisage {
        item: BrisageItem {
            id: 6491,
            quantity: 1,
            effects: vec![],
            unmapped: vec![],
        },
        focus_effect_id: Some(182),
        coefficient: 1.4829,
        coefficient_alt: None,
        runes: vec![Rune {
            item_id: 7442,
            quantity: 2,
        }],
    };
    let data = serde_json::to_value(envelope(Payload::Brisage(breaking))).unwrap()["data"].clone();
    assert_eq!(data["focus_effect_id"], json!(182));
    assert_eq!(data["runes"], json!([{ "item_id": 7442, "quantity": 2 }]));
    assert!(
        data["coefficient"].as_f64().unwrap() > 1.0,
        "a coefficient is never capped at 1"
    );
}

#[test]
fn every_payload_survives_a_round_trip() {
    let events = vec![
        envelope(Payload::HdvLots(HdvLots::resource(
            310,
            Some(47),
            vec![Lot { size: 100, price: 2984 }],
        ))),
        envelope(Payload::HdvLots(HdvLots::unique(17578, Some(11), vec![]))),
        envelope(Payload::HdvCategory(HdvCategory {
            item_type_id: 331,
            item_ids: vec![],
        })),
    ];
    for event in events {
        let text = serde_json::to_string(&event).unwrap();
        assert_eq!(serde_json::from_str::<Event>(&text).unwrap(), event);
    }
}

#[test]
fn a_normal_event_is_valid() {
    let lots = HdvLots::unique(
        33063,
        Some(331),
        vec![Offer {
            offer_id: 1,
            price: 5987,
            effects: vec![],
            unmapped: vec![],
        }],
    );
    assert!(envelope(Payload::HdvLots(lots)).validate().is_ok());
}

#[test]
fn too_many_offers_are_refused_not_truncated() {
    let offer = Offer {
        offer_id: 1,
        price: 1,
        effects: vec![],
        unmapped: vec![],
    };
    let lots = HdvLots::unique(1, None, vec![offer; MAX_OFFERS_PER_ITEM + 1]);
    let violations = envelope(Payload::HdvLots(lots)).validate().unwrap_err();
    assert!(violations.contains(&Violation::TooManyOffers {
        count: MAX_OFFERS_PER_ITEM + 1
    }));
}

#[test]
fn too_many_effects_and_too_long_texts_are_refused() {
    let many = vec![Effect::value(1, 1); MAX_EFFECTS + 1];
    let long = Effect::text(3809, &"x".repeat(MAX_TEXT_CHARS + 1));
    let offer = Offer {
        offer_id: 1,
        price: 1,
        effects: many,
        unmapped: vec![],
    };
    let other = Offer {
        offer_id: 2,
        price: 1,
        effects: vec![long],
        unmapped: vec![],
    };
    let violations = envelope(Payload::HdvLots(HdvLots::unique(1, None, vec![offer, other])))
        .validate()
        .unwrap_err();
    assert!(
        violations
            .iter()
            .any(|violation| matches!(violation, Violation::TooManyEffects { .. }))
    );
    assert!(
        violations
            .iter()
            .any(|violation| matches!(violation, Violation::TextTooLong { .. }))
    );
}

#[test]
fn a_coefficient_must_be_a_finite_non_negative_number() {
    let mut breaking = Brisage {
        item: BrisageItem {
            id: 1,
            quantity: 1,
            effects: vec![],
            unmapped: vec![],
        },
        focus_effect_id: None,
        coefficient: f32::NAN,
        coefficient_alt: None,
        runes: vec![],
    };
    assert!(envelope(Payload::Brisage(breaking.clone())).validate().is_err());
    breaking.coefficient = 1.4829;
    assert!(envelope(Payload::Brisage(breaking)).validate().is_ok());
}

proptest! {
    #[test]
    fn an_effect_round_trips_whatever_its_numbers(id in any::<i64>(), value in any::<i64>(), low in any::<i64>(), high in any::<i64>()) {
        for effect in [Effect::value(id, value), Effect::range(id, low, high), Effect::gauge(id, low, high)] {
            let text = serde_json::to_string(&effect).unwrap();
            prop_assert_eq!(serde_json::from_str::<Effect>(&text).unwrap(), effect);
        }
    }
}
