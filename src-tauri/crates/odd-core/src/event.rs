//! The envelope shared by every object the agent sends.

use serde::{Deserialize, Serialize};

use crate::brisage::Brisage;
use crate::lots::HdvLots;
use crate::percepteurs::Percepteurs;
use crate::stats::{HdvCategory, HdvStats};

/// Version of the format described in docs/json-schemas.md.
pub const SCHEMA_VERSION: u32 = 2;

/// What an event carries, tagged by its `kind`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", content = "data")]
pub enum Payload {
    /// Lots or offers of an item.
    #[serde(rename = "hdv.lots")]
    HdvLots(HdvLots),
    /// Market graph of an item.
    #[serde(rename = "hdv.stats")]
    HdvStats(HdvStats),
    /// Items of a type that are for sale.
    #[serde(rename = "hdv.category")]
    HdvCategory(HdvCategory),
    /// An item broken at the Concasseur.
    #[serde(rename = "brisage")]
    Brisage(Brisage),
    /// The tax collectors of greatest value.
    #[serde(rename = "percepteurs")]
    Percepteurs(Percepteurs),
}

impl Payload {
    /// The `kind` string of this payload.
    pub fn kind(&self) -> &'static str {
        match self {
            Self::HdvLots(_) => "hdv.lots",
            Self::HdvStats(_) => "hdv.stats",
            Self::HdvCategory(_) => "hdv.category",
            Self::Brisage(_) => "brisage",
            Self::Percepteurs(_) => "percepteurs",
        }
    }
}

/// One observation, as sent to the collector.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Event {
    /// Version of the format.
    pub schema: u32,
    /// Unique id (UUID) so a resent event is not stored twice.
    pub event_id: String,
    /// When the agent saw it (ISO 8601, UTC).
    pub observed_at: String,
    /// Game server chosen by the player.
    pub game_server: String,
    /// Version of the agent, for diagnosis.
    pub client_version: String,
    /// The data and its kind.
    #[serde(flatten)]
    pub payload: Payload,
}
