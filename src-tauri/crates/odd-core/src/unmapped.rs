//! Fields of a game message the agent does not know how to read yet.

use serde::{Deserialize, Serialize};

/// A field kept as received so it can be decoded later without a new capture.
///
/// `path` is the chain of field numbers, such as `"9.1"`. Numbers are kept in `value`, opaque bytes in `hex`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Unmapped {
    /// Chain of field numbers leading to the value.
    pub path: String,
    /// The number, when the field is a number.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub value: Option<i64>,
    /// The bytes in lowercase hexadecimal, when the field is opaque.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub hex: Option<String>,
}

impl Unmapped {
    /// An unknown numeric field.
    pub fn value(path: &str, value: i64) -> Self {
        Self {
            path: path.to_owned(),
            value: Some(value),
            hex: None,
        }
    }

    /// An unknown opaque field.
    pub fn bytes(path: &str, bytes: &[u8]) -> Self {
        let hex = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
        Self {
            path: path.to_owned(),
            value: None,
            hex: Some(hex),
        }
    }
}
