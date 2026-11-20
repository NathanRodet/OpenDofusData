//! The typed messages of the game: a type name and a payload, found inside nested messages.

use crate::protobuf::Message;

/// Start of the type URL that names every game message.
pub const TYPE_URL_PREFIX: &[u8] = b"type.ankama.com/";
const MAX_NESTING_DEPTH: usize = 4;
const URL_FIELD: u32 = 1;
const VALUE_FIELD: u32 = 2;

/// A game message: its short type name and its payload bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Envelope {
    /// The type name without its URL prefix (`jzs`, `kch`...).
    pub type_name: String,
    /// The payload, a protobuf message.
    pub payload: Vec<u8>,
}

fn as_envelope(message: &Message<'_>) -> Option<Envelope> {
    let url = message.bytes(URL_FIELD)?.strip_prefix(TYPE_URL_PREFIX)?;
    let type_name = std::str::from_utf8(url).ok()?.to_owned();
    let payload = message.bytes(VALUE_FIELD).unwrap_or_default().to_vec();
    Some(Envelope { type_name, payload })
}

/// Every envelope in a message, looking inside nested messages.
pub fn find_envelopes(message: &Message<'_>, depth: usize) -> Vec<Envelope> {
    if let Some(envelope) = as_envelope(message) {
        return vec![envelope];
    }
    if depth >= MAX_NESTING_DEPTH {
        return Vec::new();
    }
    let nested = message.fields().filter_map(|field| field.value.as_bytes());
    nested
        .filter_map(|bytes| Message::parse(bytes).ok())
        .flat_map(|inner| find_envelopes(&inner, depth + 1))
        .collect()
}

/// Reads a whole frame body and returns its envelopes, or `None` when it is not protobuf.
pub(crate) fn envelopes_of(body: &[u8]) -> Option<Vec<Envelope>> {
    Message::parse(body).ok().map(|message| find_envelopes(&message, 0))
}
