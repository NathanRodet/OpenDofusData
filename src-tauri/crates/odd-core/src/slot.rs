//! A slot is the place where only the freshest event is kept, on the client before sending and on the server.

use time::OffsetDateTime;

use crate::{Event, Payload};

/// What an event replaces: the same kind of data about the same thing on the same game server.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Slot {
    /// The offers of an item.
    HdvLots {
        /// Game server.
        server: String,
        /// The item.
        item_id: i64,
    },
    /// The market graph of an item.
    HdvStats {
        /// Game server.
        server: String,
        /// The item.
        item_id: i64,
    },
    /// The items for sale in a type.
    HdvCategory {
        /// Game server.
        server: String,
        /// The item type.
        item_type_id: i64,
    },
    /// The latest breaking of an item on a UTC day.
    Brisage {
        /// Game server.
        server: String,
        /// The item that was broken.
        item_id: i64,
        /// The UTC day, `YYYY-MM-DD`.
        day: String,
    },
    /// The tax collectors of greatest value of a game server.
    Percepteurs {
        /// Game server.
        server: String,
    },
    /// The tax collector met on a map (a map holds one: the latest sighting replaces the older one).
    PercepteurSeen {
        /// Game server.
        server: String,
        /// The map.
        map_id: i64,
    },
    /// The dialog of the tax collector of a map (the latest one replaces the older one).
    PercepteurSheet {
        /// Game server.
        server: String,
        /// The map.
        map_id: i64,
    },
}

impl Slot {
    /// The kind of data, as stored.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::HdvLots { .. } => "hdv_lots",
            Self::HdvStats { .. } => "hdv_stats",
            Self::HdvCategory { .. } => "hdv_category",
            Self::Brisage { .. } => "brisage",
            Self::Percepteurs { .. } => "percepteurs",
            Self::PercepteurSeen { .. } => "percepteur_seen",
            Self::PercepteurSheet { .. } => "percepteur_sheet",
        }
    }

    /// The game server.
    pub fn server(&self) -> &str {
        match self {
            Self::HdvLots { server, .. }
            | Self::HdvStats { server, .. }
            | Self::HdvCategory { server, .. }
            | Self::Brisage { server, .. }
            | Self::Percepteurs { server }
            | Self::PercepteurSeen { server, .. }
            | Self::PercepteurSheet { server, .. } => server,
        }
    }

    /// What the data is about, unique with the kind and the server.
    pub fn subject(&self) -> String {
        match self {
            Self::HdvLots { item_id, .. } | Self::HdvStats { item_id, .. } => item_id.to_string(),
            Self::HdvCategory { item_type_id, .. } => item_type_id.to_string(),
            Self::Brisage { item_id, day, .. } => format!("{item_id}:{day}"),
            Self::Percepteurs { .. } => "all".to_owned(),
            Self::PercepteurSeen { map_id, .. } | Self::PercepteurSheet { map_id, .. } => map_id.to_string(),
        }
    }
}

/// The slot an event belongs to. `observed_at` is the parsed `event.observed_at`.
pub fn slot_of(event: &Event, observed_at: OffsetDateTime) -> Slot {
    let server = event.game_server.clone();
    match &event.payload {
        Payload::HdvLots(lots) => Slot::HdvLots {
            server,
            item_id: lots.item_id,
        },
        Payload::HdvStats(stats) => Slot::HdvStats {
            server,
            item_id: stats.item_id,
        },
        Payload::HdvCategory(category) => Slot::HdvCategory {
            server,
            item_type_id: category.item_type_id,
        },
        Payload::Brisage(breaking) => Slot::Brisage {
            server,
            item_id: breaking.item.id,
            day: utc_day(observed_at),
        },
        Payload::Percepteurs(_) => Slot::Percepteurs { server },
        Payload::PercepteurSeen(seen) => Slot::PercepteurSeen {
            server,
            map_id: seen.map_id,
        },
        Payload::PercepteurSheet(sheet) => Slot::PercepteurSheet {
            server,
            map_id: sheet.map_id,
        },
    }
}

fn utc_day(at: OffsetDateTime) -> String {
    let date = at.to_offset(time::UtcOffset::UTC).date();
    format!("{:04}-{:02}-{:02}", date.year(), u8::from(date.month()), date.day())
}
