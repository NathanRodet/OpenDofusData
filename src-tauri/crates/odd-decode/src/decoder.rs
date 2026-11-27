//! The decoder of a play session: routes each game message to the right reader and keeps what must be remembered.

use odd_wire::{Envelope, Message};
use time::OffsetDateTime;

use crate::brisage::BrisageTracker;
use crate::issue::Decoded;
use crate::lots::LotsTracker;
use crate::messages::{
    BREAK_REQUEST, BREAK_RESULT, CATEGORY_RESPONSE, LOT_REQUEST, LOT_RESPONSE, PERCEPTEURS_RESPONSE, STATS_REQUEST,
    STATS_RESPONSE, WINDOW_ADD, WINDOW_CLOSE, WINDOW_UPDATE,
};
use crate::percepteurs::decode_percepteurs;
use crate::stats::{StatsTracker, decode_category};

/// Which way a message travelled.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    /// From the player's game to the game server.
    ToServer,
    /// From the game server to the player's game.
    ToClient,
}

/// Decodes the messages of one connection, in the order they happened.
#[derive(Debug, Default)]
pub struct Decoder {
    lots: LotsTracker,
    stats: StatsTracker,
    breaking: BrisageTracker,
}

impl Decoder {
    /// A decoder that has seen nothing yet.
    pub fn new() -> Self {
        Self::default()
    }

    /// Forgets everything remembered (a new connection starts).
    pub fn reset(&mut self) {
        *self = Self::default();
    }

    /// Decodes one message. `now` is the time of the capture, used for the 7 day window of the market graph.
    pub fn handle(&mut self, direction: Direction, envelope: &Envelope, now: OffsetDateTime) -> Decoded {
        let mut out = Decoded::default();
        let Ok(message) = Message::parse(&envelope.payload) else {
            if is_known(&envelope.type_name) {
                out.malformed(&envelope.type_name);
            }
            return out;
        };
        self.route(direction, &envelope.type_name, &message, now, &mut out);
        out
    }

    fn route(
        &mut self,
        direction: Direction,
        name: &str,
        message: &Message<'_>,
        now: OffsetDateTime,
        out: &mut Decoded,
    ) {
        match (direction, name) {
            (Direction::ToServer, LOT_REQUEST) => self.lots.on_request(message),
            (Direction::ToClient, LOT_RESPONSE) => self.lots.on_response(message, out),
            (Direction::ToServer, STATS_REQUEST) => self.stats.on_request(message),
            (Direction::ToClient, STATS_RESPONSE) => self.stats.on_response(message, now, out),
            (Direction::ToClient, CATEGORY_RESPONSE) => decode_category(message, out),
            (Direction::ToClient, PERCEPTEURS_RESPONSE) => decode_percepteurs(message, out),
            (Direction::ToClient, WINDOW_ADD | WINDOW_UPDATE) => self.breaking.on_window_item(message),
            (Direction::ToServer, BREAK_REQUEST) => self.breaking.on_request(message),
            (Direction::ToClient, BREAK_RESULT) => self.breaking.on_result(message, out),
            (_, WINDOW_CLOSE) => self.breaking.clear(),
            _ => {}
        }
    }
}

fn is_known(name: &str) -> bool {
    [
        LOT_REQUEST,
        LOT_RESPONSE,
        STATS_REQUEST,
        STATS_RESPONSE,
        CATEGORY_RESPONSE,
        PERCEPTEURS_RESPONSE,
        WINDOW_ADD,
        WINDOW_UPDATE,
        BREAK_REQUEST,
        BREAK_RESULT,
    ]
    .contains(&name)
}
