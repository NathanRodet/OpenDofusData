//! A frame is a varint length followed by that many bytes.

use crate::error::WireError;
use crate::protobuf::read_varint;

/// What the bytes at a position say about a frame.
pub(crate) enum Frame {
    /// The frame cannot be what is there, whatever follows.
    Invalid,
    /// The length is plausible but the frame is not fully buffered yet.
    Incomplete,
    /// A whole frame: `header` bytes of length, `total` bytes with the body.
    Complete { header: usize, total: usize },
}

/// Looks at the frame that would start at the beginning of `data`.
pub(crate) fn frame_at(data: &[u8], max_body: usize) -> Frame {
    let (length, header) = match read_varint(data, 0) {
        Ok(read) => read,
        Err(WireError::Truncated) => return Frame::Incomplete,
        Err(WireError::Malformed) => return Frame::Invalid,
    };
    let Ok(length) = usize::try_from(length) else {
        return Frame::Invalid;
    };
    if length == 0 || length > max_body {
        return Frame::Invalid;
    }
    let total = header + length;
    if data.len() < total {
        Frame::Incomplete
    } else {
        Frame::Complete { header, total }
    }
}
