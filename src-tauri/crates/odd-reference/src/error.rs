//! Why the reference data could not be downloaded or kept.

/// Why a reference step failed.
#[derive(Debug, thiserror::Error)]
pub enum ReferenceError {
    /// The address of DofusDB is not an http or https address.
    #[error("the address of DofusDB is not valid")]
    InvalidAddress,
    /// The HTTP client could not be prepared.
    #[error("cannot prepare the HTTP client: {0}")]
    Setup(String),
    /// DofusDB cannot be reached or answered something unexpected.
    #[error("DofusDB cannot be read: {0}")]
    Unavailable(String),
    /// The local copy could not be written.
    #[error("cannot write the local copy: {0}")]
    Disk(#[from] std::io::Error),
    /// The local copy cannot be turned into JSON.
    #[error("cannot encode the local copy: {0}")]
    Json(#[from] serde_json::Error),
}
