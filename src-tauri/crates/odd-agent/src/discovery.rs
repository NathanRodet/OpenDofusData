//! Dev mode capture: the structure of every game message, written as JSON lines for a developer to study.
//!
//! By default only numbers are kept (field numbers, integers, lengths): no text and no raw bytes.
//! The one exception is opt-in: for the message types the developer lists, opaque fields also give their first bytes
//! (hex) and packed numbers. Those bytes can be text (a name, a chat line): never list a chat type, and read the file
//! before sharing it. The files stay on the developer's PC; nothing here is sent.

use std::fs::{self, File};
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};

use odd_decode::Direction;
use odd_wire::{Envelope, Message, Value, unpack_varints};
use serde_json::{Map, Value as Json, json};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

/// How deep nested messages are described.
const MAX_DEPTH: usize = 6;
/// Largest capture file; past it nothing more is written.
pub const MAX_CAPTURE_BYTES: u64 = 100 * 1024 * 1024;
const WIRE_VARINT: u8 = 0;
const WIRE_FIXED64: u8 = 1;
const WIRE_BYTES: u8 = 2;
const WIRE_FIXED32: u8 = 5;
const NAME_TIME_LENGTH: usize = 19;
/// Bytes shown in the hex preview of a detailed opaque field.
const MAX_HEX_BYTES: usize = 64;
/// Numbers shown from a packed list of a detailed opaque field.
const MAX_PACKED_VALUES: usize = 32;

/// One game message seen on the connection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Observation {
    /// Which way it travelled.
    pub direction: Direction,
    /// The message.
    pub envelope: Envelope,
    /// When it was seen.
    pub at: OffsetDateTime,
}

fn leaf(number: u32, wire_type: u8) -> Map<String, Json> {
    let mut node = Map::new();
    node.insert("number".to_owned(), json!(number));
    node.insert("wire_type".to_owned(), json!(wire_type));
    node
}

fn wire_type_of(value: Value<'_>) -> u8 {
    match value {
        Value::Varint(_) => WIRE_VARINT,
        Value::Fixed64(_) => WIRE_FIXED64,
        Value::Bytes(_) => WIRE_BYTES,
        Value::Fixed32(_) => WIRE_FIXED32,
    }
}

fn describe_value(number: u32, value: Value<'_>, depth: usize, detailed: bool) -> Json {
    let mut node = leaf(number, wire_type_of(value));
    match value {
        Value::Varint(value) | Value::Fixed64(value) => {
            node.insert("value".to_owned(), json!(value));
        }
        Value::Fixed32(bits) => {
            node.insert("value".to_owned(), json!(bits));
        }
        Value::Bytes(bytes) => {
            node.insert("length".to_owned(), json!(bytes.len()));
            match nested(bytes, depth, detailed) {
                Some(fields) => node.insert("fields".to_owned(), Json::Array(fields)),
                None if detailed => preview(bytes, &mut node),
                None => None,
            };
        }
    }
    Json::Object(node)
}

/// The fields of `bytes` when they are a whole protobuf message (and not too deep).
fn nested(bytes: &[u8], depth: usize, detailed: bool) -> Option<Vec<Json>> {
    if depth >= MAX_DEPTH || bytes.is_empty() {
        return None;
    }
    Message::parse(bytes)
        .ok()
        .map(|message| describe_fields(&message, depth + 1, detailed))
}

fn describe_fields(message: &Message<'_>, depth: usize, detailed: bool) -> Vec<Json> {
    message
        .fields()
        .map(|field| describe_value(field.number, field.value, depth, detailed))
        .collect()
}

/// The hex of the first bytes of an opaque field, and its numbers when it is exactly a list of packed varints.
/// It can hold text: only the types the developer asked for get it.
fn preview(bytes: &[u8], node: &mut Map<String, Json>) -> Option<Json> {
    let hex: String = bytes
        .iter()
        .take(MAX_HEX_BYTES)
        .map(|byte| format!("{byte:02x}"))
        .collect();
    node.insert("hex".to_owned(), json!(hex));
    let numbers = unpack_varints(bytes).ok().filter(|numbers| !numbers.is_empty())?;
    let shown: Vec<u64> = numbers.into_iter().take(MAX_PACKED_VALUES).collect();
    node.insert("packed".to_owned(), json!(shown))
}

/// The JSON line of one message: time, direction, type, size and the structure of its fields.
/// With `detailed`, opaque fields also give their first bytes and their packed numbers.
pub fn describe_message(observation: &Observation, detailed: bool) -> Result<String, serde_json::Error> {
    let envelope = &observation.envelope;
    let fields = Message::parse(&envelope.payload)
        .map(|message| describe_fields(&message, 0, detailed))
        .unwrap_or_default();
    let direction = match observation.direction {
        Direction::ToServer => "client_to_server",
        Direction::ToClient => "server_to_client",
    };
    serde_json::to_string(&json!({
        "time": observation.at.format(&Rfc3339).unwrap_or_default(),
        "direction": direction,
        "type": envelope.type_name,
        "size": envelope.payload.len(),
        "fields": fields,
    }))
}

/// What happened to a recorded message.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Recorded {
    /// The line is in the file.
    Written,
    /// The file reached its size limit: nothing more is written.
    Full,
}

/// A capture file being written, one JSON line per message.
#[derive(Debug)]
pub struct Recorder {
    file: BufWriter<File>,
    detailed_types: Vec<String>,
    path: PathBuf,
    written: u64,
}

impl Recorder {
    /// Creates `capture-YYYY-MM-DD-HH-MM-SS.jsonl` in `directory` (made when missing).
    /// The types in `detailed_types` get the bytes and packed numbers of their opaque fields.
    pub fn create(directory: &Path, now: OffsetDateTime, detailed_types: &[String]) -> io::Result<Self> {
        fs::create_dir_all(directory)?;
        let stamp: String = now
            .format(&Rfc3339)
            .unwrap_or_default()
            .chars()
            .take(NAME_TIME_LENGTH)
            .collect();
        let path = directory.join(format!("capture-{}.jsonl", stamp.replace(['T', ':'], "-")));
        let file = BufWriter::new(File::create(&path)?);
        Ok(Self {
            file,
            detailed_types: detailed_types.to_vec(),
            path,
            written: 0,
        })
    }

    /// The file being written.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Appends the message, unless the file is full.
    pub fn record(&mut self, observation: &Observation) -> io::Result<Recorded> {
        if self.written >= MAX_CAPTURE_BYTES {
            return Ok(Recorded::Full);
        }
        let detailed = self.detailed_types.contains(&observation.envelope.type_name);
        let line = describe_message(observation, detailed).map_err(io::Error::other)?;
        writeln!(self.file, "{line}")?;
        self.file.flush()?;
        self.written += u64::try_from(line.len()).unwrap_or(u64::MAX).saturating_add(1);
        Ok(Recorded::Written)
    }
}
