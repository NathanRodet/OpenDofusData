//! TCP packet parsing and stream reassembly for the game connection.
//!
//! Pure logic: no capture and no network access, so it is tested on synthetic frames.
#![forbid(unsafe_code)]

mod flow;
mod parse;
mod reassembly;
mod stream;

pub use flow::{FlowId, FlowKey, Side, TcpSegment};
pub use parse::parse_ethernet_frame;
pub use reassembly::{MAX_FLOWS, Reassembler, StreamEvent};
pub use stream::MAX_PENDING_BYTES;
