//! Game protocol plumbing: reading protobuf and extracting messages from a reassembled stream.
//!
//! Pure logic: no network, no capture, no game message names.
#![forbid(unsafe_code)]

mod envelope;
mod error;
mod extractor;
mod frame;
mod protobuf;
mod resync;

#[cfg(feature = "testkit")]
pub mod testkit;

pub use envelope::{Envelope, TYPE_URL_PREFIX, find_envelopes};
pub use error::WireError;
pub use extractor::{EnvelopeExtractor, MAX_BUFFER_BYTES, MAX_FRAME_BYTES};
pub use protobuf::{Field, MAX_FIELDS_PER_MESSAGE, MAX_VARINT_BYTES, Message, Value, read_varint, unpack_varints};
pub use resync::RESYNC_MAX_FRAME_BYTES;
