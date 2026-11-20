//! Payload of `brisage`: one item broken at the Concasseur.

use serde::{Deserialize, Serialize};

use crate::effect::Effect;
use crate::unmapped::Unmapped;

/// The item as it was put in the Concasseur, before it was destroyed.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BrisageItem {
    /// The item.
    pub id: i64,
    /// Number of copies in the stack (one result for the whole stack).
    pub quantity: u32,
    /// Effects of the item. An effect rolled at 0 is absent.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub effects: Vec<Effect>,
    /// Fields of the item not understood yet.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub unmapped: Vec<Unmapped>,
}

/// A rune obtained.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rune {
    /// The rune's item id.
    pub item_id: i64,
    /// Number of runes.
    pub quantity: i64,
}

/// The result of breaking one item.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Brisage {
    /// The item that was broken.
    pub item: BrisageItem,
    /// Effect chosen as the focus by the player, when there is one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub focus_effect_id: Option<i64>,
    /// Breaking coefficient (0.5 is 50 %). It can exceed 1.
    pub coefficient: f32,
    /// The second number of the result, a neighbour of the coefficient whose meaning is unknown.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub coefficient_alt: Option<f32>,
    /// Runes obtained. Absent when there is none.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub runes: Vec<Rune>,
}
