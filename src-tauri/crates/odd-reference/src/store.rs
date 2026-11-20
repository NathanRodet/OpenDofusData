//! The local copy of the reference data.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::error::ReferenceError;
use crate::fetch::Reference;

const FILE_NAME: &str = "reference.json";
const TEMPORARY_NAME: &str = "reference.json.tmp";

/// The items and the moment they were downloaded.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Snapshot {
    /// Seconds since 1970-01-01 UTC.
    pub fetched_at: u64,
    /// The names.
    pub reference: Reference,
}

impl Snapshot {
    /// Whether the copy is `max_age_seconds` old or more at `now` (seconds since 1970).
    pub fn is_stale(&self, now: u64, max_age_seconds: u64) -> bool {
        now.saturating_sub(self.fetched_at) >= max_age_seconds
    }
}

/// Keeps the snapshot in a folder.
#[derive(Debug, Clone)]
pub struct ReferenceStore {
    directory: PathBuf,
}

impl ReferenceStore {
    /// A store in `directory` (created when saving).
    pub fn new(directory: PathBuf) -> Self {
        Self { directory }
    }

    /// The saved snapshot; `None` when there is none or it cannot be read.
    pub fn load(&self) -> Option<Snapshot> {
        let bytes = std::fs::read(self.directory.join(FILE_NAME)).ok()?;
        serde_json::from_slice(&bytes).ok()
    }

    /// Saves the snapshot, through a temporary file so a crash never leaves half a copy.
    pub fn save(&self, snapshot: &Snapshot) -> Result<(), ReferenceError> {
        std::fs::create_dir_all(&self.directory)?;
        let temporary = self.directory.join(TEMPORARY_NAME);
        std::fs::write(&temporary, serde_json::to_vec(snapshot)?)?;
        std::fs::rename(temporary, self.directory.join(FILE_NAME))?;
        Ok(())
    }

    /// Deletes the saved snapshot, if any.
    pub fn remove(&self) -> Result<(), ReferenceError> {
        match std::fs::remove_file(self.directory.join(FILE_NAME)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }
}
