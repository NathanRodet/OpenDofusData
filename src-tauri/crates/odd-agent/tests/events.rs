//! Making the objects to send out of what was decoded, and describing them for the logs.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_agent::{EventContext, LogCategory, build_event, describe};
use odd_core::{
    Brisage, BrisageItem, HdvCategory, HdvLots, HdvStats, Listing, Lot, Offer, Payload, Period, Periods, Points,
    SCHEMA_VERSION,
};
use time::macros::datetime;

fn offer(price: i64) -> Offer {
    Offer {
        offer_id: 1,
        price,
        effects: vec![],
        unmapped: vec![],
    }
}

fn period() -> Period {
    Period {
        sold: 0,
        median: 0,
        mean: 0.0,
    }
}

fn breaking(coefficient: f32) -> Payload {
    let item = BrisageItem {
        id: 310,
        quantity: 1,
        effects: vec![],
        unmapped: vec![],
    };
    Payload::Brisage(Brisage {
        item,
        focus_effect_id: None,
        coefficient,
        coefficient_alt: None,
        runes: vec![],
    })
}

#[test]
fn an_event_carries_the_context_and_a_utc_date() {
    let context = EventContext {
        game_server: "Kourial",
        client_version: "2.4.0",
    };
    let payload = Payload::HdvLots(HdvLots::unique(310, Some(11), vec![offer(100)]));
    let at = datetime!(2026-11-19 23:30:05 +01:00);
    let event = build_event(payload.clone(), at, "abc123".to_owned(), &context);
    assert_eq!(event.schema, SCHEMA_VERSION);
    assert_eq!(event.event_id, "abc123");
    assert_eq!(event.observed_at, "2026-11-19T22:30:05Z", "dates are sent in UTC");
    assert_eq!(
        (event.game_server.as_str(), event.client_version.as_str()),
        ("Kourial", "2.4.0")
    );
    assert_eq!(event.payload, payload);
}

#[test]
fn offers_are_counted_in_the_description() {
    let some = Payload::HdvLots(HdvLots::unique(310, Some(11), vec![offer(1), offer(2)]));
    assert_eq!(
        describe(&some),
        (LogCategory::Hdv, "2 offres pour l'objet 310".to_owned())
    );
    let one = Payload::HdvLots(HdvLots::unique(310, None, vec![offer(1)]));
    assert_eq!(describe(&one).1, "1 offre pour l'objet 310");
    let none = Payload::HdvLots(HdvLots::unique(310, None, vec![]));
    assert_eq!(describe(&none).1, "Aucune offre pour l'objet 310");
}

#[test]
fn lots_of_a_resource_are_described_by_their_sizes() {
    let lots = vec![
        Lot { size: 1, price: 10 },
        Lot { size: 10, price: 95 },
        Lot { size: 100, price: 900 },
    ];
    let payload = Payload::HdvLots(HdvLots {
        item_id: 22,
        item_type_id: Some(47),
        listing: Listing::Lots { lots },
    });
    assert_eq!(
        describe(&payload),
        (LogCategory::Hdv, "3 tailles de lots pour l'objet 22".to_owned())
    );
}

#[test]
fn stats_and_categories_are_described() {
    let stats = Payload::HdvStats(HdvStats {
        item_id: 5,
        last_purchase_at: None,
        periods: Periods {
            h24: period(),
            d7: period(),
            d30: period(),
        },
        points: Points {
            hourly: vec![],
            daily: vec![],
        },
    });
    assert_eq!(
        describe(&stats),
        (LogCategory::Hdv, "Statistiques de prix de l'objet 5".to_owned())
    );
    let category = Payload::HdvCategory(HdvCategory {
        item_type_id: 47,
        item_ids: vec![1, 2, 3],
    });
    assert_eq!(
        describe(&category),
        (LogCategory::Hdv, "3 objets en vente dans le type 47".to_owned())
    );
}

#[test]
fn a_breaking_shows_its_coefficient_as_a_percentage() {
    assert_eq!(
        describe(&breaking(0.5)),
        (
            LogCategory::Brisage,
            "Brisage de l'objet 310, coefficient 50 %".to_owned()
        )
    );
    assert_eq!(describe(&breaking(1.25)).1, "Brisage de l'objet 310, coefficient 125 %");
}

#[test]
fn descriptions_never_use_a_dash_look_alike_or_a_middle_dot() {
    for payload in [
        breaking(0.7),
        Payload::HdvCategory(HdvCategory {
            item_type_id: 1,
            item_ids: vec![],
        }),
    ] {
        let text = describe(&payload).1;
        assert!(!text.contains(['\u{2013}', '\u{2014}', '\u{00B7}']), "{text}");
    }
}

#[test]
fn event_ids_are_128_bit_hexadecimal_and_never_repeat() {
    let ids: std::collections::HashSet<String> = (0..2000).map(|_| odd_agent::new_event_id()).collect();
    assert_eq!(ids.len(), 2000);
    assert!(
        ids.iter()
            .all(|id| id.len() == 32 && id.bytes().all(|byte| byte.is_ascii_hexdigit()))
    );
}
