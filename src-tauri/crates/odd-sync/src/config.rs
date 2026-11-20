//! How the sending loop batches and retries.

use std::sync::Arc;
use std::time::Duration;

use crate::status::Notice;

/// Told about what the loop does, for the logs of the interface.
pub type Observer = Arc<dyn Fn(Notice) + Send + Sync>;

/// How the loop batches and retries.
#[derive(Debug, Clone, Copy)]
pub struct SenderConfig {
    /// How long objects are gathered before a request is made.
    pub batch_window: Duration,
    /// Most objects in a request (the server accepts 500).
    pub max_batch: usize,
    /// First wait after a failure; it doubles after each failure.
    pub backoff_start: Duration,
    /// Longest wait between two attempts.
    pub backoff_max: Duration,
}

impl Default for SenderConfig {
    fn default() -> Self {
        Self {
            batch_window: Duration::from_millis(200),
            max_batch: 500,
            backoff_start: Duration::from_secs(1),
            backoff_max: Duration::from_secs(30),
        }
    }
}
