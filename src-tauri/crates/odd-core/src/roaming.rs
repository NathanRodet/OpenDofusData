//! Payloads of the tax collectors met on a map: `percepteur.seen` (the player enters the map) and `percepteur.sheet`
//! (the player opens the dialog of one). They differ from `percepteurs`, the "Book" window.

use serde::{Deserialize, Serialize};

use crate::unmapped::Unmapped;

/// A tax collector standing on the map the player entered.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PercepteurSeen {
    /// The map (the site turns it into coordinates).
    pub map_id: i64,
    /// The sub-area of the map.
    pub sub_area_id: i64,
    /// The cell of the map where it stands.
    pub cell: i64,
    /// The direction it faces.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub direction: Option<i64>,
    /// Name of the alliance that owns it.
    pub alliance: String,
    /// Tag of the alliance.
    pub tag: String,
    /// The two ids of the name the game builds for the collector (to be turned into a text with the game's name tables).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub name_ids: Vec<i64>,
    /// The emblem of the alliance, as received (fields not understood yet).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub emblem: Vec<Unmapped>,
}

/// What the dialog of a tax collector says.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PercepteurSheet {
    /// The map where it stands.
    pub map_id: i64,
    /// The cell where it stands.
    pub cell: i64,
    /// Name of the alliance that owns it.
    pub alliance: String,
    /// Tag of the alliance.
    pub tag: String,
    /// Number of collectors the alliance has recruited.
    pub alliance_collectors: u64,
    /// Pods of items it can carry.
    pub pod_capacity: u64,
    /// Its prospecting.
    pub prospecting: u64,
    /// Pods it carries now.
    pub pods: u64,
    /// Estimated market value of what it carries, in kamas.
    pub value: u64,
}
