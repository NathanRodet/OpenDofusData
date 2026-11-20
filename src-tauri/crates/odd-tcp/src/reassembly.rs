//! Follows every game connection and hands over each direction as an ordered stream of bytes.

use std::collections::HashMap;

use crate::flow::{FlowId, FlowKey, Side, TcpSegment};
use crate::stream::{Delivery, Stream};

/// Connections followed at the same time, at most. The least recently used one is closed beyond it.
pub const MAX_FLOWS: usize = 64;

/// What the reassembler hands over.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StreamEvent {
    /// The next bytes of one direction of a connection, in order.
    Data {
        /// The connection.
        flow: FlowId,
        /// The direction.
        from: Side,
        /// The bytes.
        bytes: Vec<u8>,
    },
    /// Bytes were lost in one direction: what follows does not continue what came before.
    Gap {
        /// The connection.
        flow: FlowId,
        /// The direction.
        from: Side,
    },
    /// The connection ended (closing, reset, or too many connections).
    Closed {
        /// The connection.
        flow: FlowId,
    },
}

#[derive(Debug)]
struct Flow {
    id: FlowId,
    client: Stream,
    server: Stream,
    last_used: u64,
}

/// Reassembles the TCP streams of the game connections.
#[derive(Debug, Default)]
pub struct Reassembler {
    flows: HashMap<FlowKey, Flow>,
    next_id: u64,
    clock: u64,
}

impl Reassembler {
    /// A reassembler that follows no connection yet.
    pub fn new() -> Self {
        Self::default()
    }

    /// Takes one captured segment and returns what is now ready.
    pub fn push(&mut self, segment: TcpSegment) -> Vec<StreamEvent> {
        let mut events = Vec::new();
        if !self.flows.contains_key(&segment.key) {
            self.make_room(&mut events);
            self.open(segment.key);
        }
        self.clock += 1;
        let Some(flow) = self.flows.get_mut(&segment.key) else {
            return events;
        };
        flow.last_used = self.clock;
        let stream = if segment.from == Side::Client {
            &mut flow.client
        } else {
            &mut flow.server
        };
        for delivery in stream.push(segment.seq, segment.syn, &segment.payload) {
            events.push(into_event(flow.id, segment.from, delivery));
        }
        if segment.fin || segment.rst {
            let id = flow.id;
            self.flows.remove(&segment.key);
            events.push(StreamEvent::Closed { flow: id });
        }
        events
    }

    fn open(&mut self, key: FlowKey) {
        let id = FlowId(self.next_id);
        self.next_id += 1;
        self.flows.insert(
            key,
            Flow {
                id,
                client: Stream::default(),
                server: Stream::default(),
                last_used: self.clock,
            },
        );
    }

    fn make_room(&mut self, events: &mut Vec<StreamEvent>) {
        if self.flows.len() < MAX_FLOWS {
            return;
        }
        let oldest = self
            .flows
            .iter()
            .min_by_key(|(_, flow)| flow.last_used)
            .map(|(key, _)| *key);
        if let Some(flow) = oldest.and_then(|key| self.flows.remove(&key)) {
            events.push(StreamEvent::Closed { flow: flow.id });
        }
    }
}

fn into_event(flow: FlowId, from: Side, delivery: Delivery) -> StreamEvent {
    match delivery {
        Delivery::Data(bytes) => StreamEvent::Data { flow, from, bytes },
        Delivery::Gap => StreamEvent::Gap { flow, from },
    }
}
