//! The decoders, fed with messages shaped like the ones captured on 2026-11-19.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_core::{Effect, HdvCategory, HdvLots, Listing, Lot, Payload, Rune, Unmapped};
use odd_decode::{Decoder, Direction, Issue};
use odd_wire::Envelope;
use odd_wire::testkit::{field_bytes, field_fixed32, field_message, field_packed, field_varint};
use time::macros::datetime;

const NEGATIVE_FOUR_THOUSAND: u64 = 18_446_744_073_709_546_959;

fn message(type_name: &str, parts: &[Vec<u8>]) -> Envelope {
    Envelope {
        type_name: type_name.to_owned(),
        payload: parts.concat(),
    }
}

/// The fields of an effect (the caller wraps them in field 5 of an offer or field 7 of a window item).
fn effect(id: u64, parts: &[Vec<u8>]) -> Vec<u8> {
    [parts.concat(), field_varint(10, id)].concat()
}

fn offer(price: u64, offer_id: u64, type_id: u64, effects: Vec<Vec<u8>>) -> Vec<u8> {
    let head = [
        field_varint(1, 33063),
        field_packed(2, &[price, 0, 0, 0]),
        field_varint(3, offer_id),
        field_varint(4, type_id),
    ];
    let wrapped: Vec<u8> = effects.iter().flat_map(|inner| field_bytes(5, inner)).collect();
    field_message(1, &[head.concat(), wrapped])
}

fn run(decoder: &mut Decoder, direction: Direction, envelope: &Envelope) -> Vec<Payload> {
    decoder
        .handle(direction, envelope, datetime!(2026-11-19 19:30:32 UTC))
        .payloads
}

#[test]
fn a_resource_listing_gives_one_price_per_lot_size() {
    let entry = field_message(
        1,
        &[
            field_varint(1, 310),
            field_packed(2, &[22, 272, 2984, 34990]),
            field_varint(3, 851),
            field_varint(4, 47),
        ],
    );
    let response = message("jzs", &[entry, field_varint(2, 47), field_varint(3, 310)]);
    let out = run(&mut Decoder::new(), Direction::ToClient, &response);
    let lots = vec![
        Lot { size: 1, price: 22 },
        Lot { size: 10, price: 272 },
        Lot { size: 100, price: 2984 },
        Lot {
            size: 1000,
            price: 34990,
        },
    ];
    assert_eq!(out, vec![Payload::HdvLots(HdvLots::resource(310, Some(47), lots))]);
}

#[test]
fn a_lot_size_with_a_zero_price_does_not_exist() {
    let entry = field_message(
        1,
        &[
            field_varint(1, 34095),
            field_packed(2, &[82985, 0, 0, 0]),
            field_varint(4, 47),
        ],
    );
    let out = run(
        &mut Decoder::new(),
        Direction::ToClient,
        &message("jzs", &[entry, field_varint(3, 34095)]),
    );
    let Payload::HdvLots(lots) = &out[0] else {
        panic!("expected lots")
    };
    assert_eq!(
        lots.listing,
        Listing::Lots {
            lots: vec![Lot { size: 1, price: 82985 }]
        }
    );
}

#[test]
fn equipment_offers_keep_their_effects_in_every_form() {
    let effects = vec![
        effect(125, &[field_varint(5, 300)]),
        effect(100, &[field_message(8, &[field_varint(1, 22), field_varint(3, 18)])]),
        effect(
            2819,
            &[field_message(9, &[field_varint(2, 189_183), field_varint(4, 187_266)])],
        ),
        effect(3809, &[field_bytes(3, b"Gronouille")]),
        effect(2821, &[field_message(9, &[field_varint(1, 331), field_varint(4, 103)])]),
        effect(3832, &[field_message(12, &[field_varint(1, 10), field_varint(2, 18)])]),
        effect(3831, &[field_varint(5, NEGATIVE_FOUR_THOUSAND)]),
    ];
    let response = message(
        "jzs",
        &[
            offer(5800000, 43846, 11, effects),
            offer(5988890, 43851, 11, vec![]),
            field_varint(2, 11),
            field_varint(3, 33063),
        ],
    );
    let out = run(&mut Decoder::new(), Direction::ToClient, &response);
    let Payload::HdvLots(lots) = &out[0] else {
        panic!("expected lots")
    };
    let Listing::Offers { offers } = &lots.listing else {
        panic!("expected offers")
    };
    assert_eq!(offers.len(), 2);
    assert_eq!((offers[0].offer_id, offers[0].price), (43846, 5800000));
    assert_eq!(lots.item_type_id, Some(11));
    let found = &offers[0].effects;
    assert_eq!(found[0], Effect::value(125, 300));
    assert_eq!(found[1], Effect::range(100, 18, 22));
    assert_eq!(found[2], Effect::gauge(2819, 187_266, 189_183));
    assert_eq!(found[3], Effect::text(3809, "Gronouille"));
    let mut level = Effect::empty(2821);
    level.current = Some(103);
    level.unmapped.push(Unmapped::value("9.1", 331));
    assert_eq!(found[4], level);
    assert_eq!(
        found[5].unmapped,
        vec![Unmapped::value("12.1", 10), Unmapped::value("12.2", 18)]
    );
    assert_eq!(found[6], Effect::value(3831, -4657), "values are signed 64 bit numbers");
    assert!(offers[1].effects.is_empty());
}

#[test]
fn an_empty_answer_after_an_opened_sheet_means_no_offer() {
    let mut decoder = Decoder::new();
    run(
        &mut decoder,
        Direction::ToServer,
        &message("kcy", &[field_varint(1, 34548), field_varint(2, 1)]),
    );
    let empty = message("jzs", &[field_varint(2, 336), field_varint(3, 34548)]);
    let out = run(&mut decoder, Direction::ToClient, &empty);
    assert_eq!(out, vec![Payload::HdvLots(HdvLots::unique(34548, Some(336), vec![]))]);
}

#[test]
fn an_empty_answer_to_a_closed_sheet_is_only_an_acknowledgement() {
    let mut decoder = Decoder::new();
    run(
        &mut decoder,
        Direction::ToServer,
        &message("kcy", &[field_varint(1, 34548), field_varint(2, 1)]),
    );
    run(
        &mut decoder,
        Direction::ToServer,
        &message("kcy", &[field_varint(1, 34548)]),
    );
    let empty = message("jzs", &[field_varint(2, 336), field_varint(3, 34548)]);
    assert!(run(&mut decoder, Direction::ToClient, &empty).is_empty());
}

fn point(price: u64, item: u64, at: &str, quantity: u64) -> Vec<u8> {
    [
        field_varint(1, price),
        field_varint(2, item),
        field_bytes(3, at.as_bytes()),
        field_varint(4, quantity),
    ]
    .concat()
}

#[test]
fn market_statistics_are_computed_from_the_points() {
    let hourly = [
        ("2026-11-18T19:43:58.843003778Z", 9, 300),
        ("2026-11-19T18:09:59.606165396Z", 26, 100),
    ];
    let daily = [
        ("2026-10-21T23:59:22.796889Z", 31, 1000),
        ("2026-11-10T23:59:00Z", 40, 500),
        ("2026-11-14T23:59:00Z", 10, 200),
        ("2026-11-18T23:59:00Z", 20, 400),
    ];
    let mut parts: Vec<Vec<u8>> = hourly
        .iter()
        .map(|(at, price, quantity)| field_bytes(1, &point(*price, 310, at, *quantity)))
        .collect();
    parts.extend(
        daily
            .iter()
            .map(|(at, price, quantity)| field_bytes(3, &point(*price, 310, at, *quantity))),
    );
    let mut decoder = Decoder::new();
    run(
        &mut decoder,
        Direction::ToServer,
        &message("iqp", &[field_varint(1, 310)]),
    );
    let out = run(&mut decoder, Direction::ToClient, &message("ire", &parts));
    let Payload::HdvStats(stats) = &out[0] else {
        panic!("expected stats")
    };
    assert_eq!(stats.item_id, 310);
    assert_eq!(
        stats.last_purchase_at.as_deref(),
        Some("2026-11-19T18:09:59.606165396Z")
    );
    assert_eq!((stats.periods.h24.sold, stats.periods.h24.median), (400, 9));
    assert!((stats.periods.h24.mean - 13.25).abs() < 1e-9);
    assert_eq!(
        stats.periods.d7.sold, 600,
        "7 days start at midnight UTC seven days before the capture"
    );
    assert_eq!(stats.periods.d30.sold, 2100);
    assert_eq!(stats.points.hourly.len(), 2);
    assert_eq!(stats.points.daily[0].at, "2026-10-21T23:59:22.796889Z");
}

#[test]
fn a_category_answer_lists_the_items_for_sale() {
    let answer = message("kbj", &[field_packed(1, &[34547, 34549]), field_varint(2, 336)]);
    let out = run(&mut Decoder::new(), Direction::ToClient, &answer);
    assert_eq!(
        out,
        vec![Payload::HdvCategory(HdvCategory {
            item_type_id: 336,
            item_ids: vec![34547, 34549]
        })]
    );
}

#[test]
fn a_category_answer_without_items_is_an_empty_list() {
    let out = run(
        &mut Decoder::new(),
        Direction::ToClient,
        &message("kbj", &[field_varint(2, 301)]),
    );
    assert_eq!(
        out,
        vec![Payload::HdvCategory(HdvCategory {
            item_type_id: 301,
            item_ids: vec![]
        })]
    );
}

fn window_item(quantity: u64, item: u64, instance: u64, effects: Vec<Vec<u8>>) -> Envelope {
    let object = [
        field_varint(3, quantity),
        field_varint(4, item),
        field_varint(5, instance),
    ];
    let wrapped: Vec<u8> = effects.iter().flat_map(|inner| field_bytes(7, inner)).collect();
    let object = field_message(1, &[object.concat(), wrapped]);
    message("kch", &[field_message(3, &[object, field_varint(4, 63)])])
}

/// One entry of a breaking result: coefficient bits, instance id, runes as (quantity, item).
type ResultEntry = (u32, u64, Vec<(u64, u64)>);

fn result(entries: &[ResultEntry]) -> Envelope {
    let parts: Vec<Vec<u8>> = entries
        .iter()
        .map(|(bits, instance, runes)| {
            let mut fields = vec![
                field_fixed32(1, *bits),
                field_fixed32(2, *bits),
                field_varint(3, *instance),
            ];
            fields.extend(
                runes
                    .iter()
                    .map(|(quantity, item)| field_message(4, &[field_varint(1, *quantity), field_varint(2, *item)])),
            );
            field_message(1, &[fields.concat()])
        })
        .collect();
    message("kag", &parts)
}

const HALF: u32 = 0x3F00_0000;
const ONE_AND_A_HALF: u32 = 0x3FC0_0000;

#[test]
fn a_breaking_joins_the_item_put_in_the_window_with_its_result() {
    let mut decoder = Decoder::new();
    let add = window_item(
        1,
        16527,
        1_536_476,
        vec![
            effect(126, &[field_varint(5, 9)]),
            effect(96, &[field_message(8, &[field_varint(1, 7), field_varint(3, 5)])]),
        ],
    );
    assert!(run(&mut decoder, Direction::ToClient, &add).is_empty());
    let out = run(
        &mut decoder,
        Direction::ToClient,
        &result(&[(ONE_AND_A_HALF, 1_536_476, vec![(2, 7436), (3, 1522)])]),
    );
    let Payload::Brisage(breaking) = &out[0] else {
        panic!("expected a breaking")
    };
    assert_eq!(breaking.item.id, 16527);
    assert_eq!(
        breaking.item.effects,
        vec![Effect::value(126, 9), Effect::range(96, 5, 7)]
    );
    assert_eq!(breaking.coefficient, 1.5, "a coefficient above 1 is kept");
    assert_eq!(
        breaking.runes,
        vec![
            Rune {
                item_id: 7436,
                quantity: 2
            },
            Rune {
                item_id: 1522,
                quantity: 3
            }
        ]
    );
    assert_eq!(breaking.focus_effect_id, None);
}

#[test]
fn the_focus_chosen_by_the_player_is_kept() {
    let mut decoder = Decoder::new();
    run(
        &mut decoder,
        Direction::ToClient,
        &window_item(1, 6491, 466_028, vec![effect(182, &[field_varint(5, 2)])]),
    );
    run(
        &mut decoder,
        Direction::ToServer,
        &message("jxy", &[field_varint(1, 1), field_varint(2, 182), field_varint(3, 1)]),
    );
    let out = run(
        &mut decoder,
        Direction::ToClient,
        &result(&[(HALF, 466_028, vec![(2, 7442)])]),
    );
    let Payload::Brisage(breaking) = &out[0] else {
        panic!("expected a breaking")
    };
    assert_eq!(breaking.focus_effect_id, Some(182));
    let again = run(
        &mut decoder,
        Direction::ToClient,
        &window_item(1, 6491, 466_029, vec![]),
    );
    assert!(again.is_empty());
    run(
        &mut decoder,
        Direction::ToServer,
        &message("jxy", &[field_varint(1, 2), field_varint(3, 1)]),
    );
    let out = run(&mut decoder, Direction::ToClient, &result(&[(HALF, 466_029, vec![])]));
    let Payload::Brisage(second) = &out[0] else {
        panic!("expected a breaking")
    };
    assert_eq!(
        second.focus_effect_id, None,
        "a request without focus clears the previous focus"
    );
}

#[test]
fn three_items_broken_together_give_three_breakings_whatever_the_order() {
    let mut decoder = Decoder::new();
    for (item, instance) in [(6718, 2_145_268), (16527, 1_536_476), (674, 1_519_156)] {
        run(
            &mut decoder,
            Direction::ToClient,
            &window_item(1, item, instance, vec![]),
        );
    }
    let answer = result(&[
        (HALF, 2_145_268, vec![]),
        (ONE_AND_A_HALF, 1_519_156, vec![(1, 1523)]),
        (HALF, 1_536_476, vec![]),
    ]);
    let out = run(&mut decoder, Direction::ToClient, &answer);
    let items: Vec<i64> = out
        .iter()
        .map(|payload| match payload {
            Payload::Brisage(b) => b.item.id,
            _ => 0,
        })
        .collect();
    assert_eq!(items, vec![6718, 674, 16527]);
}

#[test]
fn a_result_for_an_unknown_instance_is_reported_not_guessed() {
    let mut decoder = Decoder::new();
    let decoded = decoder.handle(
        Direction::ToClient,
        &result(&[(HALF, 99, vec![])]),
        datetime!(2026-11-19 19:30:32 UTC),
    );
    assert!(decoded.payloads.is_empty());
    assert_eq!(decoded.issues, vec![Issue::UnknownWindowInstance { instance: 99 }]);
}

#[test]
fn closing_the_window_forgets_its_items() {
    let mut decoder = Decoder::new();
    run(&mut decoder, Direction::ToClient, &window_item(1, 6718, 5, vec![]));
    run(&mut decoder, Direction::ToServer, &message("kiq", &[]));
    let decoded = decoder.handle(
        Direction::ToClient,
        &result(&[(HALF, 5, vec![])]),
        datetime!(2026-11-19 19:30:32 UTC),
    );
    assert!(decoded.payloads.is_empty());
}

#[test]
fn an_update_changes_the_quantity_of_a_stacked_item() {
    let mut decoder = Decoder::new();
    run(
        &mut decoder,
        Direction::ToClient,
        &window_item(1, 8228, 7, vec![effect(125, &[field_varint(5, 4)])]),
    );
    let mut update = window_item(2, 8228, 7, vec![]);
    update.type_name = "kdr".to_owned();
    run(&mut decoder, Direction::ToClient, &update);
    let out = run(&mut decoder, Direction::ToClient, &result(&[(HALF, 7, vec![])]));
    let Payload::Brisage(breaking) = &out[0] else {
        panic!("expected a breaking")
    };
    assert_eq!(breaking.item.quantity, 2);
    assert_eq!(
        breaking.item.effects,
        vec![Effect::value(125, 4)],
        "the stack keeps the effects it was added with"
    );
}

#[test]
fn a_malformed_payload_is_an_issue_not_a_crash() {
    let broken = Envelope {
        type_name: "jzs".to_owned(),
        payload: vec![0x0b, 0xff],
    };
    let decoded = Decoder::new().handle(Direction::ToClient, &broken, datetime!(2026-11-19 19:30:32 UTC));
    assert!(decoded.payloads.is_empty());
    assert_eq!(
        decoded.issues,
        vec![Issue::MalformedPayload {
            type_name: "jzs".to_owned()
        }]
    );
}

#[test]
fn unknown_message_types_are_ignored() {
    let decoded = Decoder::new().handle(
        Direction::ToClient,
        &message("zzz", &[field_varint(1, 1)]),
        datetime!(2026-11-19 19:30:32 UTC),
    );
    assert!(decoded.payloads.is_empty() && decoded.issues.is_empty());
}
