//! The shapes the interface reads and writes. The names are those of `src/lib/types.ts`.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Whether the capture library of the game traffic is usable.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum NpcapState {
    /// Npcap and the capture program are there.
    Ok,
    /// Npcap is not installed.
    Missing,
}

/// What is known about the player's key.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum KeyState {
    /// No key is registered.
    Missing,
    /// The server accepts it.
    Valid,
    /// Its date has passed.
    Expired,
    /// The server refuses it.
    Refused,
}

/// The state of the link with the collector.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ConnectionKind {
    /// The last request worked.
    Connected,
    /// Nothing is known yet.
    #[default]
    Connecting,
    /// The collector cannot be reached, or there is no key.
    Offline,
}

/// A new version of the application.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateInfo {
    /// The version offered.
    pub version: String,
    /// The file that would be downloaded.
    pub file_name: String,
    /// 0 to 100 while downloading.
    pub progress: Option<u8>,
    /// Megabytes downloaded.
    pub downloaded_mb: Option<f32>,
    /// Megabytes to download.
    pub total_mb: Option<f32>,
}

/// The state shown at the top of the interface.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppStatus {
    /// The version of this application.
    pub app_version: String,
    /// Whether the capture library is usable.
    pub npcap: NpcapState,
    /// What is known about the key.
    pub key: KeyState,
    /// Days left before the key expires, when known.
    pub key_expires_in_days: Option<i64>,
    /// The link with the collector.
    pub connection: ConnectionKind,
    /// How long the last request took.
    pub latency_ms: Option<u64>,
    /// A new version, when there is one.
    pub update: Option<UpdateInfo>,
}

/// A counter with its target.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Progress {
    /// Done so far.
    pub done: u64,
    /// To do in all.
    pub total: u64,
}

/// What was sent to the collector.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct SentProgress {
    /// Answered by the collector.
    pub done: u64,
    /// Answered or waiting.
    pub total: u64,
    /// Waiting to be sent.
    pub pending: u64,
    /// Failed sends and refused objects.
    pub errors: u64,
}

/// What was received from the collector.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReceivedProgress {
    /// How many objects.
    pub count: u64,
    /// When the last one came.
    pub last_at: Option<String>,
}

/// The three blocks of counters of the logs page.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SyncProgress {
    /// The reference data downloaded from DofusDB.
    pub reference: Progress,
    /// What was sent.
    pub sent: SentProgress,
    /// What was received.
    pub received: ReceivedProgress,
}

/// Where a line of the logs comes from.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LogOrigin {
    /// Game data analysed by the agent.
    Game,
    /// Something received from the collector.
    Server,
}

/// The family of a line of the logs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EntryCategory {
    /// The auction house.
    Hdv,
    /// Breaking items.
    Brisage,
    /// Anything else.
    Other,
}

/// How a line of the logs ended.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EntryStatus {
    /// Understood.
    Analyzed,
    /// Nothing to do.
    Ignored,
    /// Something went wrong.
    Error,
}

/// One line of the logs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LogEntry {
    /// Grows with every line of the session.
    pub id: u64,
    /// ISO 8601, UTC.
    pub at: String,
    /// Where it comes from.
    pub origin: LogOrigin,
    /// The family.
    pub category: EntryCategory,
    /// How it ended.
    pub status: EntryStatus,
    /// A short sentence.
    pub summary: String,
    /// The exact object sent or received, or null.
    pub payload: Value,
    /// What happened to the object.
    pub payload_note: String,
}

/// The answer of the connection test.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ConnectionTest {
    /// Whether the key works.
    pub ok: bool,
    /// What to tell the player.
    pub message: String,
}
