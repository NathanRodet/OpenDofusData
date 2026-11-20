//! Reading of protobuf wire bytes.
#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, missing_docs)]

use odd_wire::testkit::{field_bytes, field_fixed32, field_varint, varint};
use odd_wire::{Message, Value, WireError, read_varint, unpack_varints};
use proptest::prelude::*;

proptest! {
    #[test]
    fn a_varint_round_trips(value in any::<u64>()) {
        let bytes = varint(value);
        let (read, end) = read_varint(&bytes, 0).unwrap();
        prop_assert_eq!((read, end), (value, bytes.len()));
    }
}

#[test]
fn a_cut_varint_is_truncated_not_malformed() {
    assert_eq!(read_varint(&[0x80], 0), Err(WireError::Truncated));
    assert_eq!(read_varint(&[], 0), Err(WireError::Truncated));
}

#[test]
fn a_varint_over_ten_bytes_is_malformed() {
    assert_eq!(read_varint(&[0xff; 11], 0), Err(WireError::Malformed));
}

#[test]
fn nested_fields_are_found_by_number() {
    let inner = [field_varint(1, 33018), field_varint(3, 58557)].concat();
    let data = [field_bytes(1, &inner), field_varint(2, 331)].concat();
    let message = Message::parse(&data).unwrap();
    assert_eq!(message.varint(2), Some(331));
    let nested = Message::parse(message.bytes(1).unwrap()).unwrap();
    assert_eq!((nested.varint(1), nested.varint(3)), (Some(33018), Some(58557)));
}

#[test]
fn a_repeated_field_keeps_every_occurrence_in_order() {
    let data = [field_varint(5, 1), field_varint(5, 2), field_varint(5, 3)].concat();
    let message = Message::parse(&data).unwrap();
    let values: Vec<u64> = message.all(5).filter_map(|value| value.as_varint()).collect();
    assert_eq!(values, vec![1, 2, 3]);
}

#[test]
fn negative_numbers_arrive_as_huge_unsigned_varints_and_read_back_signed() {
    let data = field_varint(10, 18_446_744_073_709_546_959);
    assert_eq!(Message::parse(&data).unwrap().signed(10), Some(-4657));
}

#[test]
fn a_fixed32_field_reads_as_a_float() {
    let data = field_fixed32(1, 0x3F00_0000);
    assert_eq!(Message::parse(&data).unwrap().float(1), Some(0.5));
}

#[test]
fn packed_varints_are_unpacked() {
    let packed = [varint(22), varint(272), varint(2984), varint(34990)].concat();
    assert_eq!(unpack_varints(&packed).unwrap(), vec![22, 272, 2984, 34990]);
}

#[test]
fn a_group_wire_type_is_refused() {
    assert_eq!(Message::parse(&[0x0b]).unwrap_err(), WireError::Malformed);
}

#[test]
fn field_number_zero_is_refused() {
    assert_eq!(Message::parse(&[0x00, 0x01]).unwrap_err(), WireError::Malformed);
}

#[test]
fn a_length_beyond_the_data_is_truncated() {
    let mut data = field_bytes(1, b"abcdef");
    data.truncate(data.len() - 2);
    assert_eq!(Message::parse(&data).unwrap_err(), WireError::Truncated);
}

#[test]
fn bytes_value_exposes_its_slice() {
    let data = field_bytes(1, b"hello");
    let message = Message::parse(&data).unwrap();
    assert_eq!(message.fields().next().unwrap().value, Value::Bytes(b"hello"));
}
