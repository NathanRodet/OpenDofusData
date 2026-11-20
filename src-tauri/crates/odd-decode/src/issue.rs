//! Things the decoders could not make sense of. They are reported, never guessed around.

use odd_core::Payload;

/// A problem met while decoding one message.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum Issue {
    /// The payload is not valid protobuf.
    #[error("the {type_name} message is not valid protobuf")]
    MalformedPayload {
        /// The message type.
        type_name: String,
    },
    /// A field the decoder needs is missing.
    #[error("the {type_name} message has no field {field}")]
    MissingField {
        /// The message type.
        type_name: String,
        /// The missing field number.
        field: u32,
    },
    /// A breaking result names an item that was not seen entering the window.
    #[error("breaking result for the unknown window item {instance}")]
    UnknownWindowInstance {
        /// The instance id of the item.
        instance: i64,
    },
}

/// What one message produced.
#[derive(Debug, Default, PartialEq)]
pub struct Decoded {
    /// Objects ready to send.
    pub payloads: Vec<Payload>,
    /// Problems to show in the logs.
    pub issues: Vec<Issue>,
}

impl Decoded {
    pub(crate) fn missing(&mut self, type_name: &str, field: u32) {
        self.issues.push(Issue::MissingField {
            type_name: type_name.to_owned(),
            field,
        });
    }

    pub(crate) fn malformed(&mut self, type_name: &str) {
        self.issues.push(Issue::MalformedPayload {
            type_name: type_name.to_owned(),
        });
    }
}
