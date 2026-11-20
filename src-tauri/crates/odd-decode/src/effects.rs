//! Reading of an effect (the "jet" of an item) and of fields nobody understands yet.

use odd_core::{Effect, Unmapped};
use odd_wire::{Message, Value};

const EFFECT_ID: u32 = 10;
const VALUE: u32 = 5;
const RANGE: u32 = 8;
const RANGE_MAX: u32 = 1;
const RANGE_MIN: u32 = 3;
const GAUGE: u32 = 9;
const GAUGE_CURRENT: u32 = 4;
const GAUGE_MAX: u32 = 2;
const TEXT: u32 = 3;
const MAX_UNMAPPED_DEPTH: usize = 3;

/// Reads the fields of an effect. `None` when there is no effect id.
pub(crate) fn decode_effect(raw: &[u8]) -> Option<Effect> {
    let message = Message::parse(raw).ok()?;
    let mut effect = Effect::empty(message.signed(EFFECT_ID)?);
    effect.value = message.signed(VALUE);
    read_range(&message, &mut effect);
    read_gauge(&message, &mut effect);
    read_text(&message, &mut effect);
    effect
        .unmapped
        .extend(unmapped_fields(&message, &[EFFECT_ID, VALUE, RANGE, GAUGE, TEXT]));
    Some(effect)
}

fn read_range(message: &Message<'_>, effect: &mut Effect) {
    let Some(bytes) = message.bytes(RANGE) else { return };
    let Ok(range) = Message::parse(bytes) else {
        effect.unmapped.push(Unmapped::bytes(&RANGE.to_string(), bytes));
        return;
    };
    effect.max = range.signed(RANGE_MAX);
    effect.min = range.signed(RANGE_MIN);
    effect
        .unmapped
        .extend(nested_unmapped(RANGE, &range, &[RANGE_MAX, RANGE_MIN]));
}

fn read_gauge(message: &Message<'_>, effect: &mut Effect) {
    let Some(bytes) = message.bytes(GAUGE) else { return };
    let Ok(gauge) = Message::parse(bytes) else {
        effect.unmapped.push(Unmapped::bytes(&GAUGE.to_string(), bytes));
        return;
    };
    effect.current = gauge.signed(GAUGE_CURRENT);
    effect.max = gauge.signed(GAUGE_MAX);
    effect
        .unmapped
        .extend(nested_unmapped(GAUGE, &gauge, &[GAUGE_CURRENT, GAUGE_MAX]));
}

fn read_text(message: &Message<'_>, effect: &mut Effect) {
    let Some(bytes) = message.bytes(TEXT) else { return };
    match std::str::from_utf8(bytes) {
        Ok(text) => effect.text = Some(text.to_owned()),
        Err(_) => effect.unmapped.push(Unmapped::bytes(&TEXT.to_string(), bytes)),
    }
}

fn nested_unmapped(parent: u32, message: &Message<'_>, known: &[u32]) -> Vec<Unmapped> {
    unmapped_under(&parent.to_string(), message, known, 1)
}

/// Every field of `message` that is not in `known`, as unmapped fields.
pub(crate) fn unmapped_fields(message: &Message<'_>, known: &[u32]) -> Vec<Unmapped> {
    unmapped_under("", message, known, 0)
}

fn unmapped_under(prefix: &str, message: &Message<'_>, known: &[u32], depth: usize) -> Vec<Unmapped> {
    let unknown = message.fields().filter(|field| !known.contains(&field.number));
    unknown
        .flat_map(|field| {
            let path = if prefix.is_empty() {
                field.number.to_string()
            } else {
                format!("{prefix}.{}", field.number)
            };
            unmapped_value(&path, field.value, depth)
        })
        .collect()
}

fn unmapped_value(path: &str, value: Value<'_>, depth: usize) -> Vec<Unmapped> {
    match value {
        Value::Varint(number) => vec![Unmapped::value(path, number as i64)],
        Value::Fixed32(bits) => vec![Unmapped::value(path, i64::from(bits))],
        Value::Fixed64(bits) => vec![Unmapped::value(path, bits as i64)],
        Value::Bytes(bytes) => unmapped_bytes(path, bytes, depth),
    }
}

fn unmapped_bytes(path: &str, bytes: &[u8], depth: usize) -> Vec<Unmapped> {
    match Message::parse(bytes) {
        Ok(inner) if depth < MAX_UNMAPPED_DEPTH && inner.fields().next().is_some() => {
            unmapped_under(path, &inner, &[], depth + 1)
        }
        _ => vec![Unmapped::bytes(path, bytes)],
    }
}
