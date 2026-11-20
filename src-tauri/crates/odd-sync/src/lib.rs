//! Sending the decoded objects to the collector: a queue that keeps the freshest object of each slot, batches,
//! retries with a growing delay.
#![forbid(unsafe_code)]

mod client;
mod config;
mod outbox;
mod sender;
mod status;

pub use client::{EventResult, KeyInfo, ServerStatus, SyncClient, SyncError};
pub use config::{Observer, SenderConfig};
pub use outbox::{MAX_PENDING_EVENTS, Outbox, PushOutcome};
pub use sender::{Sender, spawn_sender};
pub use status::{Notice, SyncSnapshot, SyncStatus};
