//! The offers of an item: `kcy` opens or closes a sheet, `jzs` answers.

use std::collections::HashSet;

use odd_core::{Effect, HdvLots, Lot, Offer, Payload, Unmapped};
use odd_wire::{Message, unpack_varints};

use crate::effects::{decode_effect, unmapped_fields};
use crate::issue::Decoded;
use crate::messages::{LOT_RESPONSE, LOT_SIZES, lot};

const KNOWN_ENTRY_FIELDS: [u32; 5] = [
    lot::ENTRY_ITEM,
    lot::ENTRY_PRICES,
    lot::ENTRY_OFFER,
    lot::ENTRY_TYPE,
    lot::ENTRY_EFFECT,
];

/// Remembers which item sheets are open, so an empty answer can be told from a closing acknowledgement.
#[derive(Debug, Default)]
pub(crate) struct LotsTracker {
    open: HashSet<i64>,
}

impl LotsTracker {
    pub(crate) fn on_request(&mut self, request: &Message<'_>) {
        let Some(item) = request.signed(lot::REQUEST_ITEM) else {
            return;
        };
        if request.varint(lot::REQUEST_OPEN).is_some_and(|flag| flag != 0) {
            self.open.insert(item);
        } else {
            self.open.remove(&item);
        }
    }

    pub(crate) fn on_response(&mut self, response: &Message<'_>, out: &mut Decoded) {
        let entries: Vec<Message<'_>> = response
            .all(lot::ENTRY)
            .filter_map(|value| value.as_bytes())
            .filter_map(|bytes| Message::parse(bytes).ok())
            .collect();
        let item = response
            .signed(lot::RESPONSE_ITEM)
            .or_else(|| entries.first().and_then(|entry| entry.signed(lot::ENTRY_ITEM)));
        let item_type = response
            .signed(lot::RESPONSE_TYPE)
            .or_else(|| entries.first().and_then(|entry| entry.signed(lot::ENTRY_TYPE)));
        let Some(item) = item else {
            return out.missing(LOT_RESPONSE, lot::RESPONSE_ITEM);
        };
        if entries.is_empty() {
            if self.open.remove(&item) {
                out.payloads
                    .push(Payload::HdvLots(HdvLots::unique(item, item_type, Vec::new())));
            }
            return;
        }
        let lots = listing(item, item_type, &entries, out);
        out.payloads.push(Payload::HdvLots(lots));
    }
}

fn listing(item: i64, item_type: Option<i64>, entries: &[Message<'_>], out: &mut Decoded) -> HdvLots {
    let is_resource = entries.len() == 1 && entries.iter().all(|entry| entry.bytes(lot::ENTRY_EFFECT).is_none());
    if is_resource {
        return HdvLots::resource(item, item_type, lots_of(&entries[0]));
    }
    let offers = entries.iter().filter_map(|entry| offer_of(entry, out)).collect();
    HdvLots::unique(item, item_type, offers)
}

fn prices_of(entry: &Message<'_>) -> Vec<i64> {
    let packed = entry
        .bytes(lot::ENTRY_PRICES)
        .and_then(|bytes| unpack_varints(bytes).ok());
    packed
        .unwrap_or_default()
        .into_iter()
        .map(|price| price as i64)
        .collect()
}

fn lots_of(entry: &Message<'_>) -> Vec<Lot> {
    let sizes = LOT_SIZES.iter();
    sizes
        .zip(prices_of(entry))
        .filter(|(_, price)| *price != 0)
        .map(|(size, price)| Lot { size: *size, price })
        .collect()
}

fn offer_of(entry: &Message<'_>, out: &mut Decoded) -> Option<Offer> {
    let Some(price) = prices_of(entry).first().copied() else {
        out.missing(LOT_RESPONSE, lot::ENTRY_PRICES);
        return None;
    };
    let effects: Vec<Effect> = entry
        .all(lot::ENTRY_EFFECT)
        .filter_map(|value| value.as_bytes())
        .filter_map(decode_effect)
        .collect();
    let unmapped: Vec<Unmapped> = unmapped_fields(entry, &KNOWN_ENTRY_FIELDS);
    Some(Offer {
        offer_id: entry.signed(lot::ENTRY_OFFER).unwrap_or_default(),
        price,
        effects,
        unmapped,
    })
}
