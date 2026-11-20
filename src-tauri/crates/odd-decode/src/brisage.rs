//! The Concasseur: items enter the window (`kch`, `kdr`), the player breaks them (`jxy`), the result comes (`kag`).

use std::collections::HashMap;

use odd_core::{Brisage, BrisageItem, Effect, Payload, Rune, Unmapped};
use odd_wire::Message;

use crate::effects::{decode_effect, unmapped_fields};
use crate::issue::{Decoded, Issue};
use crate::messages::{BREAK_RESULT, breaking};

const KNOWN_OBJECT_FIELDS: [u32; 4] = [
    breaking::OBJECT_QUANTITY,
    breaking::OBJECT_ITEM,
    breaking::OBJECT_INSTANCE,
    breaking::OBJECT_EFFECT,
];

#[derive(Debug)]
struct WindowItem {
    id: i64,
    quantity: u32,
    effects: Vec<Effect>,
    unmapped: Vec<Unmapped>,
}

/// Remembers what is in the window. The result of a breaking only names items by instance id, which
/// changes at every connection, so the item and its effects are those seen when it entered the window.
#[derive(Debug, Default)]
pub(crate) struct BrisageTracker {
    window: HashMap<i64, WindowItem>,
    focus: Option<i64>,
}

impl BrisageTracker {
    pub(crate) fn clear(&mut self) {
        self.window.clear();
        self.focus = None;
    }

    pub(crate) fn on_request(&mut self, request: &Message<'_>) {
        self.focus = request.signed(breaking::REQUEST_FOCUS);
    }

    /// An item enters the window, or its quantity changes.
    pub(crate) fn on_window_item(&mut self, body: &Message<'_>) {
        let object = body
            .bytes(breaking::WINDOW_BODY)
            .and_then(|bytes| Message::parse(bytes).ok())
            .and_then(|outer| {
                outer
                    .bytes(breaking::WINDOW_OBJECT)
                    .and_then(|bytes| Message::parse(bytes).ok())
            });
        let Some(object) = object else { return };
        let (Some(id), Some(instance)) = (
            object.signed(breaking::OBJECT_ITEM),
            object.signed(breaking::OBJECT_INSTANCE),
        ) else {
            return;
        };
        let quantity = object
            .varint(breaking::OBJECT_QUANTITY)
            .and_then(|value| u32::try_from(value).ok())
            .unwrap_or(1);
        let effects: Vec<Effect> = object
            .all(breaking::OBJECT_EFFECT)
            .filter_map(|value| value.as_bytes())
            .filter_map(decode_effect)
            .collect();
        let unmapped = unmapped_fields(&object, &KNOWN_OBJECT_FIELDS);
        match self.window.get_mut(&instance) {
            Some(known) => known.quantity = quantity,
            None => {
                self.window.insert(
                    instance,
                    WindowItem {
                        id,
                        quantity,
                        effects,
                        unmapped,
                    },
                );
            }
        }
    }

    /// One breaking per entry of the result.
    pub(crate) fn on_result(&mut self, result: &Message<'_>, out: &mut Decoded) {
        let entries = result.all(breaking::RESULT_ENTRY).filter_map(|value| value.as_bytes());
        for entry in entries.filter_map(|bytes| Message::parse(bytes).ok()) {
            self.break_one(&entry, out);
        }
        self.focus = None;
    }

    fn break_one(&mut self, entry: &Message<'_>, out: &mut Decoded) {
        let Some(coefficient) = entry.float(breaking::ENTRY_COEFFICIENT) else {
            return out.missing(BREAK_RESULT, breaking::ENTRY_COEFFICIENT);
        };
        let instance = entry.signed(breaking::ENTRY_INSTANCE).unwrap_or_default();
        let Some(item) = self.window.remove(&instance) else {
            return out.issues.push(Issue::UnknownWindowInstance { instance });
        };
        out.payloads.push(Payload::Brisage(Brisage {
            item: BrisageItem {
                id: item.id,
                quantity: item.quantity,
                effects: item.effects,
                unmapped: item.unmapped,
            },
            focus_effect_id: self.focus,
            coefficient,
            coefficient_alt: entry.float(breaking::ENTRY_COEFFICIENT_ALT),
            runes: runes_of(entry),
        }));
    }
}

fn runes_of(entry: &Message<'_>) -> Vec<Rune> {
    let messages = entry
        .all(breaking::ENTRY_RUNE)
        .filter_map(|value| value.as_bytes())
        .filter_map(|bytes| Message::parse(bytes).ok());
    messages
        .filter_map(|rune| {
            Some(Rune {
                item_id: rune.signed(breaking::RUNE_ITEM)?,
                quantity: rune.signed(breaking::RUNE_QUANTITY)?,
            })
        })
        .collect()
}
