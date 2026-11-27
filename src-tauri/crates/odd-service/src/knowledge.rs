//! What the application knows about the key and the link with the collector.

use odd_agent::{LogCategory, LogLine, LogStatus};
use serde_json::Value;
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

use crate::check::CheckResult;
use crate::dto::{ConnectionKind, EntryCategory, EntryStatus, KeyState, LogEntry, LogOrigin};

const SECONDS_PER_DAY: i64 = 86_400;

/// What the last answers of the collector told.
#[derive(Debug, Default)]
pub struct Knowledge {
    expires_at: Option<OffsetDateTime>,
    refused: bool,
    /// The link with the collector.
    pub connection: ConnectionKind,
    /// How long the last key check took.
    pub latency_ms: Option<u64>,
}

impl Knowledge {
    /// Nothing is known yet; without a key there is nothing to connect.
    pub fn fresh(has_key: bool) -> Self {
        Self {
            connection: if has_key {
                ConnectionKind::Connecting
            } else {
                ConnectionKind::Offline
            },
            ..Self::default()
        }
    }

    /// Takes the answer of a key check.
    pub fn apply(&mut self, result: &CheckResult) {
        match result {
            CheckResult::Valid { expires_at, latency_ms } => {
                (self.expires_at, self.refused, self.latency_ms) = (*expires_at, false, Some(*latency_ms));
                self.connection = ConnectionKind::Connected;
            }
            CheckResult::Refused => (self.refused, self.connection) = (true, ConnectionKind::Connected),
            CheckResult::Unreachable | CheckResult::InvalidAddress => self.connection = ConnectionKind::Offline,
        }
    }

    /// The state of the key. `sending_refused` is true when a send was refused for the key.
    pub fn key_state(&self, has_key: bool, sending_refused: bool, now: OffsetDateTime) -> KeyState {
        match self.expires_at {
            _ if !has_key => KeyState::Missing,
            _ if self.refused || sending_refused => KeyState::Refused,
            Some(date) if date <= now => KeyState::Expired,
            _ => KeyState::Valid,
        }
    }

    /// Whole days left, rounded up, when the date is known.
    pub fn days_left(&self, now: OffsetDateTime) -> Option<i64> {
        let seconds = (self.expires_at? - now).whole_seconds();
        Some((seconds.max(0) + SECONDS_PER_DAY - 1) / SECONDS_PER_DAY)
    }
}

/// A line of the logs, in the shape the interface reads.
pub fn to_entry(id: u64, line: &LogLine) -> LogEntry {
    LogEntry {
        id,
        at: line.at.format(&Rfc3339).unwrap_or_default(),
        origin: LogOrigin::Game,
        category: match line.category {
            Some(LogCategory::Hdv) => EntryCategory::Hdv,
            Some(LogCategory::Brisage) => EntryCategory::Brisage,
            Some(LogCategory::Percepteurs) => EntryCategory::Percepteurs,
            None => EntryCategory::Other,
        },
        status: match line.status {
            LogStatus::Analyzed => EntryStatus::Analyzed,
            LogStatus::Ignored => EntryStatus::Ignored,
            LogStatus::Error => EntryStatus::Error,
        },
        summary: line.summary.clone(),
        payload: line.payload.clone().unwrap_or(Value::Null),
        payload_note: line.note.clone(),
    }
}
