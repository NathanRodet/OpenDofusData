//! The decoders against the real captures of 2026-11-19 (structure only, rebuilt as protobuf bytes).
//!
//! Every expected number below was checked by hand against the screenshot taken during the capture.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use std::path::Path;

use odd_core::{Brisage, Effect, HdvLots, Listing, Offer, Payload};
use odd_decode::{Decoder, Direction};
use odd_wire::Envelope;
use odd_wire::testkit::{field_fixed32, field_message, field_packed, field_varint};
use serde_json::Value;
use time::macros::datetime;

fn encode_fields(nodes: &[Value]) -> Vec<u8> {
    nodes.iter().flat_map(encode_node).collect()
}

fn encode_node(node: &Value) -> Vec<u8> {
    let number = u32::try_from(node["number"].as_u64().unwrap()).unwrap();
    match node["wire_type"].as_u64().unwrap() {
        0 => field_varint(number, node["value"].as_u64().unwrap()),
        5 => field_fixed32(number, u32::try_from(node["value"].as_u64().unwrap()).unwrap()),
        _ => encode_bytes(number, node),
    }
}

fn encode_bytes(number: u32, node: &Value) -> Vec<u8> {
    if let Some(children) = node["fields"].as_array() {
        return field_message(number, &[encode_fields(children)]);
    }
    if let Some(packed) = node["packed"].as_array() {
        let values: Vec<u64> = packed.iter().map(|value| value.as_u64().unwrap()).collect();
        return field_packed(number, &values);
    }
    odd_wire::testkit::field_bytes(
        number,
        &vec![0; usize::try_from(node["length"].as_u64().unwrap_or(0)).unwrap()],
    )
}

fn replay(name: &str) -> Vec<Payload> {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(format!("{name}.jsonl"));
    let mut decoder = Decoder::new();
    let mut out = Vec::new();
    for line in std::fs::read_to_string(path).unwrap().lines() {
        let record: Value = serde_json::from_str(line).unwrap();
        let direction = if record["direction"] == "client_to_server" {
            Direction::ToServer
        } else {
            Direction::ToClient
        };
        let envelope = Envelope {
            type_name: record["type"].as_str().unwrap().to_owned(),
            payload: encode_fields(record["fields"].as_array().unwrap()),
        };
        let decoded = decoder.handle(direction, &envelope, datetime!(2026-11-19 19:30:32 UTC));
        assert!(decoded.issues.is_empty(), "{name}: {:?}", decoded.issues);
        out.extend(decoded.payloads);
    }
    out
}

fn offers(payload: &Payload) -> (&HdvLots, &Vec<Offer>) {
    let Payload::HdvLots(lots) = payload else {
        panic!("expected lots")
    };
    let Listing::Offers { offers } = &lots.listing else {
        panic!("expected offers")
    };
    (lots, offers)
}

fn offer_at_price(offers: &[Offer], price: i64) -> &Offer {
    offers.iter().find(|offer| offer.price == price).unwrap()
}

fn effect(offer: &Offer, id: i64) -> &Effect {
    offer.effects.iter().find(|effect| effect.effect_id == id).unwrap()
}

fn breaking(payload: &Payload) -> &Brisage {
    let Payload::Brisage(breaking) = payload else {
        panic!("expected a breaking")
    };
    breaking
}

#[test]
fn bones_have_the_four_lot_prices_of_the_screen() {
    let out = replay("hdv-ressource");
    let Payload::HdvLots(lots) = &out[0] else {
        panic!("expected lots")
    };
    assert_eq!((lots.item_id, lots.item_type_id), (310, Some(47)));
    let Listing::Lots { lots } = &lots.listing else {
        panic!("expected lots")
    };
    let found: Vec<(u32, i64)> = lots.iter().map(|lot| (lot.size, lot.price)).collect();
    assert_eq!(found, vec![(1, 22), (10, 272), (100, 2984), (1000, 34990)]);
}

#[test]
fn equipment_offers_carry_the_stats_shown_in_the_tooltips() {
    let out = replay("hdv-equipement");
    assert_eq!(out.len(), 3, "the three sheets, and the empty acknowledgements ignored");
    let (scythe, scythe_offers) = offers(&out[0]);
    assert_eq!(
        (scythe.item_id, scythe.item_type_id, scythe_offers.len()),
        (32117, Some(22), 24)
    );
    let first = offer_at_price(scythe_offers, 102_000_000);
    let stat = |id| effect(first, id).value.unwrap();
    assert_eq!(
        [
            stat(124),
            stat(138),
            stat(115),
            stat(112),
            stat(753),
            stat(752),
            stat(416)
        ],
        [51, 112, 3, 11, 17, 16, 37]
    );
    assert_eq!(
        (stat(2803), stat(2807), stat(179), stat(2990)),
        (4, 3, 40, 1),
        "penalties keep a positive value"
    );
    let (_, boots) = offers(&out[1]);
    assert_eq!(boots.len(), 8);
    let chaloeil = offer_at_price(boots, 5_988_890);
    assert_eq!(effect(chaloeil, 125).value, Some(300));
    assert_eq!(effect(chaloeil, 420).value, Some(18));
    let (_, others) = offers(&out[2]);
    let indicible = offer_at_price(others, 5_650_000);
    let wanted = [
        (125, 325),
        (430, 20),
        (428, 20),
        (426, 18),
        (422, 16),
        (424, 16),
        (752, 8),
        (213, 6),
        (212, 6),
        (128, 1),
        (117, 1),
        (182, 1),
    ];
    for (id, value) in wanted {
        assert_eq!(effect(indicible, id).value, Some(value), "effect {id}");
    }
}

#[test]
fn the_big_mount_list_is_one_message_with_all_its_offers() {
    let out = replay("hdv-monture");
    let (lots, mounts) = offers(&out[0]);
    assert_eq!((lots.item_id, lots.item_type_id, mounts.len()), (33063, Some(331), 801));
    let count = |price| mounts.iter().filter(|offer| offer.price == price).count();
    assert_eq!(
        [count(5987), count(5988), count(5993), count(5994)],
        [4, 4, 4, 110],
        "same as the screen"
    );
    assert_eq!(mounts.iter().map(|offer| offer.price).min(), Some(5987));
    let named = mounts
        .iter()
        .filter(|offer| {
            offer
                .effects
                .iter()
                .any(|effect| effect.text.as_deref() == Some("Test"))
        })
        .count();
    assert_eq!(named, 21, "21 mounts carry a name in the capture");
    let negative = mounts
        .iter()
        .flat_map(|offer| &offer.effects)
        .filter(|effect| effect.effect_id == 3831)
        .filter_map(|effect| effect.value)
        .any(|value| value < 0);
    assert!(negative, "signed values are read as signed");
}

#[test]
fn the_market_graph_recomputes_the_numbers_of_the_screen() {
    let out = replay("hdv-graphique");
    let Payload::HdvStats(stats) = &out[0] else {
        panic!("expected stats")
    };
    assert_eq!(stats.item_id, 310);
    assert_eq!((stats.points.hourly.len(), stats.points.daily.len()), (19, 30));
    assert_eq!(
        (
            stats.periods.h24.sold,
            stats.periods.h24.median,
            stats.periods.h24.mean as i64
        ),
        (15163, 25, 21)
    );
    assert_eq!(
        (
            stats.periods.d7.sold,
            stats.periods.d7.median,
            stats.periods.d7.mean as i64
        ),
        (41751, 21, 18)
    );
    assert_eq!((stats.periods.d30.sold, stats.periods.d30.median), (151_417, 20));
    assert!(
        (stats.periods.d30.mean - 451.548).abs() < 0.001,
        "the list shows it rounded to 452"
    );
    assert_eq!(
        stats.last_purchase_at.as_deref(),
        Some("2026-11-19T18:09:59.606165396Z")
    );
}

#[test]
fn an_item_without_offer_is_told_from_the_closing_acknowledgements() {
    let out = replay("hdv-sans-offre");
    assert_eq!(out.len(), 2);
    let (first, listed) = offers(&out[0]);
    assert_eq!((first.item_id, first.item_type_id, listed.len()), (34547, Some(336), 1));
    assert_eq!(listed[0].price, 90_000);
    assert_eq!(out[1], Payload::HdvLots(HdvLots::unique(34548, Some(336), vec![])));
}

#[test]
fn categories_list_the_items_for_sale() {
    let out = replay("hdv-recherche");
    let ids: Vec<(i64, Vec<i64>)> = out
        .iter()
        .map(|payload| match payload {
            Payload::HdvCategory(category) => (category.item_type_id, category.item_ids.clone()),
            _ => panic!("expected a category"),
        })
        .collect();
    assert_eq!(ids[0], (336, vec![34547, 34549]));
    assert_eq!(
        ids[1],
        (335, vec![34544, 34545, 34546, 34539, 34540, 34541, 34542, 34543])
    );
}

#[test]
fn a_breaking_has_the_jet_the_coefficient_and_the_runes_of_the_screen() {
    let out = replay("brisage-jet");
    let scythe = breaking(&out[0]);
    assert_eq!(scythe.item.id, 8127);
    assert_eq!(
        scythe.item.effects,
        vec![
            Effect::value(125, 20),
            Effect::value(115, 2),
            Effect::value(426, 2),
            Effect::range(91, 4, 5)
        ]
    );
    assert!((scythe.coefficient - 0.183_339).abs() < 1e-5, "shown as 18 %");
    assert_eq!(
        scythe
            .runes
            .iter()
            .map(|rune| (rune.item_id, rune.quantity))
            .collect::<Vec<_>>(),
        vec![(1523, 1)]
    );
}

#[test]
fn two_bows_with_different_rolls_make_two_breakings() {
    let out = replay("brisage-lot");
    assert_eq!(out.len(), 2);
    let (first, second) = (breaking(&out[0]), breaking(&out[1]));
    assert_eq!((first.item.id, second.item.id), (329, 329));
    assert!((first.coefficient - 0.405_24).abs() < 1e-4 && (second.coefficient - 0.404_95).abs() < 1e-4);
    let chance = |breaking: &Brisage| {
        breaking
            .item
            .effects
            .iter()
            .find(|effect| effect.effect_id == 123)
            .and_then(|effect| effect.value)
    };
    assert_eq!(
        (chance(first), chance(second)),
        (Some(19), Some(18)),
        "each result keeps the roll of its own item"
    );
    assert!(
        first.item.effects.contains(&Effect::value(157, 10)) && first.item.effects.contains(&Effect::range(100, 8, 12))
    );
    let runes: Vec<(i64, i64)> = first.runes.iter().map(|rune| (rune.item_id, rune.quantity)).collect();
    assert_eq!(runes, vec![(1525, 4), (7433, 1), (1524, 4)]);
}

#[test]
fn three_items_broken_together_keep_their_own_coefficient_and_runes() {
    let out = replay("brisage-multi");
    let items: Vec<i64> = out.iter().map(|payload| breaking(payload).item.id).collect();
    assert_eq!(
        items,
        vec![6718, 16527, 674],
        "the removed item is not broken, so it gives nothing"
    );
    let (chacha, hammer, axe) = (breaking(&out[0]), breaking(&out[1]), breaking(&out[2]));
    assert_eq!((chacha.coefficient, chacha.runes.len()), (0.5, 0));
    assert!(
        hammer.coefficient > 1.48 && hammer.coefficient < 1.49,
        "148 %, never capped"
    );
    assert_eq!(
        hammer
            .runes
            .iter()
            .map(|rune| (rune.item_id, rune.quantity))
            .collect::<Vec<_>>(),
        vec![(7436, 2), (1522, 3)]
    );
    assert!(
        hammer.item.effects.iter().all(|effect| effect.effect_id != 125),
        "an effect rolled at 0 is not sent"
    );
    assert_eq!(axe.runes.len(), 4);
}

#[test]
fn the_focus_of_the_player_is_kept_on_the_breaking() {
    let out = replay("brisage-focus");
    let bow = breaking(&out[0]);
    assert_eq!((bow.item.id, bow.focus_effect_id), (6491, Some(182)));
    assert_eq!(
        bow.runes
            .iter()
            .map(|rune| (rune.item_id, rune.quantity))
            .collect::<Vec<_>>(),
        vec![(7442, 2)]
    );
    assert!(bow.item.effects.contains(&Effect::value(182, 2)) && bow.item.effects.contains(&Effect::range(95, 2, 4)));
}
