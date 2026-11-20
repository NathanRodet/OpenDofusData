//! Reading of protobuf wire bytes: varints, fields and messages.

use crate::error::WireError;

/// Longest varint of a 64 bit number.
pub const MAX_VARINT_BYTES: usize = 10;
/// Most fields read from one message, so a hostile message cannot make a huge list.
pub const MAX_FIELDS_PER_MESSAGE: usize = 200_000;
const MAX_FIELD_NUMBER: u64 = (1 << 29) - 1;
const WIRE_VARINT: u64 = 0;
const WIRE_FIXED64: u64 = 1;
const WIRE_BYTES: u64 = 2;
const WIRE_FIXED32: u64 = 5;
const WIRE_TYPE_MASK: u64 = 7;
const TAG_SHIFT: u32 = 3;
const VARINT_PAYLOAD_MASK: u8 = 0x7f;
const VARINT_CONTINUATION: u8 = 0x80;
const VARINT_PAYLOAD_BITS: u32 = 7;
const FIXED32_BYTES: usize = 4;
const FIXED64_BYTES: usize = 8;

/// Reads a varint at `position`. Returns the value and the position after it.
pub fn read_varint(data: &[u8], position: usize) -> Result<(u64, usize), WireError> {
    let mut value = 0u64;
    for index in 0..MAX_VARINT_BYTES {
        let byte = *data.get(position + index).ok_or(WireError::Truncated)?;
        let shift = VARINT_PAYLOAD_BITS * u32::try_from(index).map_err(|_| WireError::Malformed)?;
        value |= u64::from(byte & VARINT_PAYLOAD_MASK) << shift;
        if byte & VARINT_CONTINUATION == 0 {
            return Ok((value, position + index + 1));
        }
    }
    Err(WireError::Malformed)
}

/// Splits packed varints (a list of numbers written back to back).
pub fn unpack_varints(bytes: &[u8]) -> Result<Vec<u64>, WireError> {
    let mut values = Vec::new();
    let mut position = 0;
    while position < bytes.len() {
        let (value, next) = read_varint(bytes, position)?;
        values.push(value);
        position = next;
    }
    Ok(values)
}

/// The value of one field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Value<'a> {
    /// A number written as a varint.
    Varint(u64),
    /// Eight fixed bytes.
    Fixed64(u64),
    /// Length-delimited bytes: text, packed numbers or a nested message.
    Bytes(&'a [u8]),
    /// Four fixed bytes (a 32 bit float is written this way).
    Fixed32(u32),
}

impl<'a> Value<'a> {
    /// The number, when this is a varint.
    pub fn as_varint(&self) -> Option<u64> {
        match self {
            Self::Varint(value) => Some(*value),
            _ => None,
        }
    }

    /// The bytes, when this is a length-delimited field.
    pub fn as_bytes(&self) -> Option<&'a [u8]> {
        match self {
            Self::Bytes(bytes) => Some(bytes),
            _ => None,
        }
    }
}

/// A field: its number and its value.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Field<'a> {
    /// The field number.
    pub number: u32,
    /// The value.
    pub value: Value<'a>,
}

/// A parsed message: its fields in the order they were written.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Message<'a> {
    fields: Vec<Field<'a>>,
}

impl<'a> Message<'a> {
    /// Reads every field of `data`.
    pub fn parse(data: &'a [u8]) -> Result<Self, WireError> {
        let mut fields = Vec::new();
        let mut position = 0;
        while position < data.len() {
            if fields.len() >= MAX_FIELDS_PER_MESSAGE {
                return Err(WireError::Malformed);
            }
            let (field, next) = read_field(data, position)?;
            fields.push(field);
            position = next;
        }
        Ok(Self { fields })
    }

    /// Every field, in order.
    pub fn fields(&self) -> impl Iterator<Item = &Field<'a>> {
        self.fields.iter()
    }

    /// The values of every occurrence of a field.
    pub fn all(&self, number: u32) -> impl Iterator<Item = Value<'a>> + '_ {
        self.fields
            .iter()
            .filter(move |field| field.number == number)
            .map(|field| field.value)
    }

    /// The first varint of a field.
    pub fn varint(&self, number: u32) -> Option<u64> {
        self.all(number).find_map(|value| value.as_varint())
    }

    /// The first varint of a field, read as a signed 64 bit number.
    pub fn signed(&self, number: u32) -> Option<i64> {
        self.varint(number).map(|value| value as i64)
    }

    /// The first length-delimited value of a field.
    pub fn bytes(&self, number: u32) -> Option<&'a [u8]> {
        self.all(number).find_map(|value| value.as_bytes())
    }

    /// The first four-byte value of a field, read as a float.
    pub fn float(&self, number: u32) -> Option<f32> {
        self.all(number).find_map(|value| match value {
            Value::Fixed32(bits) => Some(f32::from_bits(bits)),
            _ => None,
        })
    }
}

fn read_field(data: &[u8], position: usize) -> Result<(Field<'_>, usize), WireError> {
    let (tag, position) = read_varint(data, position)?;
    let number = tag >> TAG_SHIFT;
    if number == 0 || number > MAX_FIELD_NUMBER {
        return Err(WireError::Malformed);
    }
    let number = u32::try_from(number).map_err(|_| WireError::Malformed)?;
    let (value, next) = read_value(data, position, tag & WIRE_TYPE_MASK)?;
    Ok((Field { number, value }, next))
}

fn read_value(data: &[u8], position: usize, wire_type: u64) -> Result<(Value<'_>, usize), WireError> {
    match wire_type {
        WIRE_VARINT => read_varint(data, position).map(|(value, next)| (Value::Varint(value), next)),
        WIRE_FIXED64 => read_fixed(data, position, FIXED64_BYTES).map(|(bits, next)| (Value::Fixed64(bits), next)),
        WIRE_FIXED32 => {
            let (bits, next) = read_fixed(data, position, FIXED32_BYTES)?;
            let bits = u32::try_from(bits).map_err(|_| WireError::Malformed)?;
            Ok((Value::Fixed32(bits), next))
        }
        WIRE_BYTES => read_bytes(data, position),
        _ => Err(WireError::Malformed),
    }
}

fn read_fixed(data: &[u8], position: usize, width: usize) -> Result<(u64, usize), WireError> {
    let bytes = data.get(position..position + width).ok_or(WireError::Truncated)?;
    let value = bytes
        .iter()
        .rev()
        .fold(0u64, |value, byte| (value << 8) | u64::from(*byte));
    Ok((value, position + width))
}

fn read_bytes(data: &[u8], position: usize) -> Result<(Value<'_>, usize), WireError> {
    let (length, position) = read_varint(data, position)?;
    let length = usize::try_from(length).map_err(|_| WireError::Malformed)?;
    let end = position.checked_add(length).ok_or(WireError::Malformed)?;
    let bytes = data.get(position..end).ok_or(WireError::Truncated)?;
    Ok((Value::Bytes(bytes), end))
}
