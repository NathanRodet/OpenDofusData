//! What the agent tells the interface for its logs, in French.

use std::sync::Arc;

use odd_core::Event;
use odd_sync::{Notice, ServerStatus};
use serde_json::Value;
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

use crate::events::{LogCategory, describe, item_id, item_type_id};

/// The note of an object the collector stored.
pub const NOTE_SENT: &str = "Envoyé au serveur";
/// The summary of a failed send.
pub const SUMMARY_SEND_FAILED: &str = "Envoi impossible pour le moment";

/// Told about each line of the logs.
pub type LogSink = Arc<dyn Fn(LogLine) + Send + Sync>;

/// How a line of the logs ended.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LogStatus {
    /// Understood, and sent or waiting to be sent.
    Analyzed,
    /// Understood but nothing to do (the server holds fresher data).
    Ignored,
    /// Something went wrong.
    Error,
}

/// One line of the logs.
#[derive(Debug, Clone, PartialEq)]
pub struct LogLine {
    /// When it happened.
    pub at: OffsetDateTime,
    /// The family, when the line is about game data.
    pub category: Option<LogCategory>,
    /// How it ended.
    pub status: LogStatus,
    /// A short sentence.
    pub summary: String,
    /// The exact object sent, when there is one.
    pub payload: Option<Value>,
    /// What happened to the object.
    pub note: String,
    /// The item the line is about, when there is one: the interface may show its name.
    pub item_id: Option<i64>,
    /// The type of items the line is about (a whole category of the auction house), when there is one.
    pub item_type_id: Option<i64>,
}

/// A line about something that is not game data (a failure of the capture or of the sending).
pub fn problem(summary: &str, note: &str) -> LogLine {
    LogLine {
        at: OffsetDateTime::now_utc(),
        category: None,
        status: LogStatus::Error,
        summary: summary.to_owned(),
        payload: None,
        note: note.to_owned(),
        item_id: None,
        item_type_id: None,
    }
}

/// A line that only informs (the dev mode capture started, for instance): not game data and not a failure.
pub fn notice(summary: &str, note: &str) -> LogLine {
    LogLine {
        status: LogStatus::Analyzed,
        ..problem(summary, note)
    }
}

/// An object that is understood but not sent because no key is registered.
pub fn unsent(event: &Event) -> LogLine {
    about(
        event,
        LogStatus::Analyzed,
        "Non envoyé: aucune clé enregistrée".to_owned(),
    )
}

/// The line for something the sending loop reports.
pub fn from_notice(notice: Notice) -> LogLine {
    match notice {
        Notice::Delivered { event, status } => delivered(&event, &status),
        Notice::Failed { reason, waiting } => problem(
            SUMMARY_SEND_FAILED,
            &format!("{waiting} en attente, nouvel essai plus tard ({reason})"),
        ),
        Notice::KeyRefused => problem(
            "Clé refusée par le serveur",
            "Plus rien n'est envoyé tant que la clé n'est pas changée",
        ),
    }
}

fn delivered(event: &Event, status: &ServerStatus) -> LogLine {
    match status {
        ServerStatus::Stored => about(event, LogStatus::Analyzed, NOTE_SENT.to_owned()),
        ServerStatus::Ignored => about(
            event,
            LogStatus::Ignored,
            "Ignoré: le serveur a déjà une donnée plus récente".to_owned(),
        ),
        ServerStatus::Rejected(reason) => about(event, LogStatus::Error, format!("Refusé par le serveur: {reason}")),
        ServerStatus::Failed => about(
            event,
            LogStatus::Error,
            "Le serveur n'a pas pu l'enregistrer".to_owned(),
        ),
    }
}

fn about(event: &Event, status: LogStatus, note: String) -> LogLine {
    let (category, summary) = describe(&event.payload);
    LogLine {
        at: OffsetDateTime::parse(&event.observed_at, &Rfc3339).unwrap_or_else(|_| OffsetDateTime::now_utc()),
        category: Some(category),
        status,
        summary,
        payload: serde_json::to_value(event).ok(),
        note,
        item_id: item_id(&event.payload),
        item_type_id: item_type_id(&event.payload),
    }
}
