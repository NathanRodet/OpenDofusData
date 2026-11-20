//! Errors of the service.

use std::io;

/// Why an operation of the service failed.
#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    /// A file could not be read or written.
    #[error("file error: {0}")]
    Io(#[from] io::Error),
    /// The settings or the logs cannot be written as JSON.
    #[error("cannot write the data: {0}")]
    Json(#[from] serde_json::Error),
    /// The sending could not be prepared (for instance a wrong server address).
    #[error("cannot prepare the sending: {0}")]
    Sync(#[from] odd_sync::SyncError),
    /// Looking for or downloading an update failed.
    #[error("update error: {0}")]
    Update(#[from] odd_update::UpdateError),
    /// There is no update to download: look for one first.
    #[error("there is no update to download")]
    NoUpdate,
}
