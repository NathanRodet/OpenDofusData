//! The transport of captured frames from the worker to the agent: a length (4 bytes, little endian), then the frame.

use std::io::{self, Read};

/// Largest frame accepted: far above the biggest Ethernet frame, small enough to refuse a corrupt length at once.
pub const MAX_FRAME_BYTES: usize = 256 * 1024;
const LENGTH_BYTES: usize = 4;

/// The frame transport failed.
#[derive(Debug, thiserror::Error)]
pub enum IpcError {
    /// The stream ended in the middle of a frame.
    #[error("the stream ended in the middle of a frame")]
    Truncated,
    /// A frame announces a length no real frame has.
    #[error("a frame announces {length} bytes, more than the {MAX_FRAME_BYTES} allowed")]
    FrameTooLong {
        /// The announced length.
        length: usize,
    },
    /// Reading failed.
    #[error("cannot read the stream: {0}")]
    Io(#[from] io::Error),
}

/// A frame, ready to be written on the stream.
pub fn encode_frame(frame: &[u8]) -> Vec<u8> {
    let length = u32::try_from(frame.len()).unwrap_or(u32::MAX);
    let mut out = Vec::with_capacity(LENGTH_BYTES + frame.len());
    out.extend_from_slice(&length.to_le_bytes());
    out.extend_from_slice(frame);
    out
}

/// Reads the frames of a stream, whatever the size of the pieces the stream gives.
#[derive(Debug)]
pub struct FrameReader<R> {
    reader: R,
}

impl<R: Read> FrameReader<R> {
    /// A reader over `reader`.
    pub fn new(reader: R) -> Self {
        Self { reader }
    }

    /// The next frame, or `None` when the stream ended cleanly between two frames.
    pub fn next_frame(&mut self) -> Result<Option<Vec<u8>>, IpcError> {
        let mut length = [0_u8; LENGTH_BYTES];
        match self.fill(&mut length)? {
            0 => return Ok(None),
            LENGTH_BYTES => {}
            _ => return Err(IpcError::Truncated),
        }
        let length = usize::try_from(u32::from_le_bytes(length)).unwrap_or(usize::MAX);
        if length > MAX_FRAME_BYTES {
            return Err(IpcError::FrameTooLong { length });
        }
        let mut frame = vec![0_u8; length];
        if self.fill(&mut frame)? != length {
            return Err(IpcError::Truncated);
        }
        Ok(Some(frame))
    }

    /// Fills `buffer` as far as the stream allows and returns how many bytes were read.
    fn fill(&mut self, buffer: &mut [u8]) -> Result<usize, IpcError> {
        let mut filled = 0;
        while filled < buffer.len() {
            match self.reader.read(&mut buffer[filled..]) {
                Ok(0) => break,
                Ok(count) => filled += count,
                Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
                Err(error) => return Err(error.into()),
            }
        }
        Ok(filled)
    }
}
