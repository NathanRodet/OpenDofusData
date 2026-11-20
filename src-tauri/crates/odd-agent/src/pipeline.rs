//! Follows every game connection from raw frames to decoded objects.

use std::collections::HashMap;

use odd_decode::{Decoded, Decoder, Direction};
use odd_tcp::{FlowId, Reassembler, Side, StreamEvent, parse_ethernet_frame};
use odd_wire::EnvelopeExtractor;
use time::OffsetDateTime;

/// What is remembered about one connection: the messages being cut out of each direction, and the decoder.
#[derive(Debug, Default)]
struct Session {
    to_server: EnvelopeExtractor,
    to_client: EnvelopeExtractor,
    decoder: Decoder,
}

impl Session {
    fn extractor(&mut self, from: Side) -> &mut EnvelopeExtractor {
        match from {
            Side::Client => &mut self.to_server,
            Side::Server => &mut self.to_client,
        }
    }

    /// Cuts the messages out of `bytes` and decodes them in the order they came.
    fn feed(&mut self, from: Side, bytes: &[u8], now: OffsetDateTime, out: &mut Decoded) {
        let direction = if from == Side::Client {
            Direction::ToServer
        } else {
            Direction::ToClient
        };
        for envelope in self.extractor(from).feed(bytes) {
            let decoded = self.decoder.handle(direction, &envelope, now);
            out.payloads.extend(decoded.payloads);
            out.issues.extend(decoded.issues);
        }
    }
}

/// Turns captured Ethernet frames into decoded objects.
#[derive(Debug)]
pub struct Pipeline {
    server_port: u16,
    reassembler: Reassembler,
    sessions: HashMap<FlowId, Session>,
}

impl Pipeline {
    /// A pipeline for the connections to or from `server_port`.
    pub fn new(server_port: u16) -> Self {
        Self {
            server_port,
            reassembler: Reassembler::new(),
            sessions: HashMap::new(),
        }
    }

    /// Takes one captured frame and returns the objects it completed. Frames that are not the game are ignored.
    pub fn handle_frame(&mut self, frame: &[u8], now: OffsetDateTime) -> Decoded {
        let mut out = Decoded::default();
        let Some(segment) = parse_ethernet_frame(frame, self.server_port) else {
            return out;
        };
        for event in self.reassembler.push(segment) {
            self.apply(event, now, &mut out);
        }
        out
    }

    fn apply(&mut self, event: StreamEvent, now: OffsetDateTime, out: &mut Decoded) {
        match event {
            StreamEvent::Data { flow, from, bytes } => {
                self.sessions.entry(flow).or_default().feed(from, &bytes, now, out)
            }
            StreamEvent::Gap { flow, from } => self.sessions.entry(flow).or_default().extractor(from).reset(),
            StreamEvent::Closed { flow } => {
                self.sessions.remove(&flow);
            }
        }
    }
}
