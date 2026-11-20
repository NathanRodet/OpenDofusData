//! What the sending loop reports: counters for the interface and notices for the logs.

use std::sync::Mutex;

use odd_core::Event;

use crate::client::ServerStatus;

/// The counters of the sending loop since the application started.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct SyncSnapshot {
    /// Objects the server stored.
    pub stored: u64,
    /// Objects the server already held fresher.
    pub ignored: u64,
    /// Objects the server refused.
    pub rejected: u64,
    /// Sends that failed and were or will be tried again.
    pub failed_attempts: u64,
    /// Objects waiting to be sent.
    pub pending: usize,
    /// Objects forgotten because too many were waiting.
    pub dropped: usize,
    /// The server refuses the key: nothing is sent until the key changes.
    pub key_refused: bool,
}

/// The counters, shared between the sending loop and the interface.
#[derive(Debug, Default)]
pub struct SyncStatus {
    inner: Mutex<SyncSnapshot>,
}

impl SyncStatus {
    /// The counters now.
    pub fn snapshot(&self) -> SyncSnapshot {
        self.inner.lock().map(|snapshot| *snapshot).unwrap_or_default()
    }

    pub(crate) fn update(&self, change: impl FnOnce(&mut SyncSnapshot)) {
        if let Ok(mut snapshot) = self.inner.lock() {
            change(&mut snapshot);
        }
    }
}

/// Something the interface may want to show in its logs.
#[derive(Debug, Clone)]
pub enum Notice {
    /// The server answered about one object.
    Delivered {
        /// The object.
        event: Box<Event>,
        /// What the server did with it.
        status: ServerStatus,
    },
    /// A send failed and will be tried again.
    Failed {
        /// Why, without any personal data.
        reason: String,
        /// How many objects wait.
        waiting: usize,
    },
    /// The server refuses the key: nothing is sent until it changes.
    KeyRefused,
}
