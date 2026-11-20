//! Builders of protobuf bytes, to write tests without a game.

use crate::envelope::TYPE_URL_PREFIX;

const VARINT_PAYLOAD_MASK: u64 = 0x7f;
const VARINT_CONTINUATION: u8 = 0x80;
const VARINT_PAYLOAD_BITS: u32 = 7;
const WIRE_VARINT: u64 = 0;
const WIRE_BYTES: u64 = 2;
const WIRE_FIXED32: u64 = 5;
const TAG_SHIFT: u32 = 3;
const OUTER_CHILD_FIELD: u32 = 3;
const URL_FIELD: u32 = 1;
const VALUE_FIELD: u32 = 2;

/// A varint.
pub fn varint(mut value: u64) -> Vec<u8> {
    let mut bytes = Vec::new();
    while value > VARINT_PAYLOAD_MASK {
        bytes.push((value & VARINT_PAYLOAD_MASK) as u8 | VARINT_CONTINUATION);
        value >>= VARINT_PAYLOAD_BITS;
    }
    bytes.push(value as u8);
    bytes
}

fn tag(number: u32, wire_type: u64) -> Vec<u8> {
    varint((u64::from(number) << TAG_SHIFT) | wire_type)
}

/// A varint field.
pub fn field_varint(number: u32, value: u64) -> Vec<u8> {
    [tag(number, WIRE_VARINT), varint(value)].concat()
}

/// A length-delimited field.
pub fn field_bytes(number: u32, content: &[u8]) -> Vec<u8> {
    [tag(number, WIRE_BYTES), varint(content.len() as u64), content.to_vec()].concat()
}

/// A nested message field built from the encoded fields of the child.
pub fn field_message(number: u32, children: &[Vec<u8>]) -> Vec<u8> {
    field_bytes(number, &children.concat())
}

/// A four-byte field.
pub fn field_fixed32(number: u32, value: u32) -> Vec<u8> {
    [tag(number, WIRE_FIXED32), value.to_le_bytes().to_vec()].concat()
}

/// A field holding packed varints.
pub fn field_packed(number: u32, values: &[u64]) -> Vec<u8> {
    let packed: Vec<u8> = values.iter().flat_map(|value| varint(*value)).collect();
    field_bytes(number, &packed)
}

/// The typed wrapper of a game message: a type URL and a payload.
pub fn any_message(type_name: &str, payload: &[u8]) -> Vec<u8> {
    let url = [TYPE_URL_PREFIX, type_name.as_bytes()].concat();
    [field_bytes(URL_FIELD, &url), field_bytes(VALUE_FIELD, payload)].concat()
}

/// An outer message holding typed messages as children.
pub fn outer_message(children: &[Vec<u8>]) -> Vec<u8> {
    children
        .iter()
        .flat_map(|child| field_bytes(OUTER_CHILD_FIELD, child))
        .collect()
}

/// A length prefix followed by the body.
pub fn frame(body: &[u8]) -> Vec<u8> {
    [varint(body.len() as u64), body.to_vec()].concat()
}

/// A complete frame carrying one game message.
pub fn envelope_frame(type_name: &str, payload: &[u8]) -> Vec<u8> {
    frame(&outer_message(&[any_message(type_name, payload)]))
}
