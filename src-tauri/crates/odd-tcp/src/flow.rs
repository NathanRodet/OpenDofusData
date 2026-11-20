//! What identifies a connection and what a captured segment carries.
//!
//! Addresses are only used to tell connections apart. They are never printed: the `Debug` forms hide them.

use std::fmt;
use std::net::SocketAddr;

/// Who sent a segment.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Side {
    /// The player's computer.
    Client,
    /// The game server.
    Server,
}

/// One TCP connection, the same for both directions.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct FlowKey {
    client: SocketAddr,
    server: SocketAddr,
}

impl FlowKey {
    /// The connection between a client address and a server address.
    pub fn new(client: SocketAddr, server: SocketAddr) -> Self {
        Self { client, server }
    }
}

impl fmt::Debug for FlowKey {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("FlowKey(..)")
    }
}

/// Identifies one life of a connection. A connection that closes and reopens gets a new identifier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct FlowId(pub(crate) u64);

/// One TCP segment of the game connection.
#[derive(Clone, PartialEq, Eq)]
pub struct TcpSegment {
    /// The connection it belongs to.
    pub key: FlowKey,
    /// Who sent it.
    pub from: Side,
    /// Sequence number of its first byte (or of the SYN).
    pub seq: u32,
    /// The bytes it carries.
    pub payload: Vec<u8>,
    /// The connection is being opened.
    pub syn: bool,
    /// The sender closes its side.
    pub fin: bool,
    /// The connection is reset.
    pub rst: bool,
}

impl fmt::Debug for TcpSegment {
    /// Shows the size only, never the bytes (they can hold what players typed).
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("TcpSegment")
            .field("from", &self.from)
            .field("seq", &self.seq)
            .field("len", &self.payload.len())
            .field("syn", &self.syn)
            .field("fin", &self.fin)
            .field("rst", &self.rst)
            .finish()
    }
}
