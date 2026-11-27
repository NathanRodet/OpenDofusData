//! Payload of `percepteurs`: the window of the tax collectors of greatest value, both tabs.

use serde::{Deserialize, Serialize};

/// One line of the window.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Percepteur {
    /// Name of the alliance that owns the collector.
    pub alliance: String,
    /// Tag of the alliance.
    pub tag: String,
    /// Pseudo of the player who placed the collector (not shown in the window, sent by the game).
    pub owner: String,
    /// Estimated value, in kamas.
    pub value: u64,
    /// Id of the sub-area (the window shows its name).
    pub sub_area_id: i64,
    /// Horizontal coordinate of the map.
    pub x: i32,
    /// Vertical coordinate of the map.
    pub y: i32,
}

/// What the window shows: the greatest collectors of each tab, in the order the game sends them.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Percepteurs {
    /// The "Classique" tab.
    pub classic: Vec<Percepteur>,
    /// The "Donjon" tab.
    pub dungeon: Vec<Percepteur>,
}
