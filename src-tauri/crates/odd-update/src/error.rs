//! Why looking for or downloading an update failed.

/// Why an update step failed.
#[derive(Debug, thiserror::Error)]
pub enum UpdateError {
    /// The address of the releases is not an http or https address.
    #[error("the address of the releases is not valid")]
    InvalidAddress,
    /// The HTTP client could not be prepared.
    #[error("cannot prepare the HTTP client: {0}")]
    Setup(String),
    /// GitHub cannot be reached or answered something unexpected.
    #[error("the releases cannot be read: {0}")]
    Unavailable(String),
    /// The release has an installer but no checksum file.
    #[error("the release has no checksum file")]
    MissingChecksum,
    /// The checksum file does not hold a SHA-256.
    #[error("the checksum file is not a SHA-256")]
    BadChecksum,
    /// A file to download is not on https (nor on the address of the releases).
    #[error("a file to download is not on a trusted address")]
    UntrustedUrl,
    /// The installer is bigger than anything this application would ever ship.
    #[error("the installer is too big")]
    TooBig,
    /// The downloaded file is not the one announced.
    #[error("the downloaded file does not match its checksum")]
    ChecksumMismatch,
    /// The file could not be written.
    #[error("cannot write the installer: {0}")]
    Disk(#[from] std::io::Error),
}
