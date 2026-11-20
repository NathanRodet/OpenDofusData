//! Errors of the wire layer.

/// Why bytes could not be read as protobuf.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum WireError {
    /// The data ends before the value is complete: more bytes may fix it.
    #[error("the data ends before the value is complete")]
    Truncated,
    /// The data cannot be protobuf, whatever follows.
    #[error("the data is not valid protobuf")]
    Malformed,
}
