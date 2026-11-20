//! One effect of an item: a stat, a weapon effect, a gauge or a text.

use serde::{Deserialize, Serialize};

use crate::unmapped::Unmapped;

/// An effect, identified by the game's effect id.
///
/// Only the keys that exist are present. Penalties have their own effect id with a positive value.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Effect {
    /// The game's effect id.
    pub effect_id: i64,
    /// A plain value.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub value: Option<i64>,
    /// Lower end of a range, or nothing.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub min: Option<i64>,
    /// Upper end of a range, or the maximum of a gauge.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max: Option<i64>,
    /// Current value of a gauge.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub current: Option<i64>,
    /// Text of the game, such as the name of a mount.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    /// Parts of the effect not understood yet.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub unmapped: Vec<Unmapped>,
}

impl Effect {
    fn bare(effect_id: i64) -> Self {
        Self {
            effect_id,
            value: None,
            min: None,
            max: None,
            current: None,
            text: None,
            unmapped: Vec::new(),
        }
    }

    /// An effect with a plain value.
    pub fn value(effect_id: i64, value: i64) -> Self {
        Self {
            value: Some(value),
            ..Self::bare(effect_id)
        }
    }

    /// An effect with a range, such as "18 to 22".
    pub fn range(effect_id: i64, min: i64, max: i64) -> Self {
        Self {
            min: Some(min),
            max: Some(max),
            ..Self::bare(effect_id)
        }
    }

    /// An effect with a current value and a maximum.
    pub fn gauge(effect_id: i64, current: i64, max: i64) -> Self {
        Self {
            current: Some(current),
            max: Some(max),
            ..Self::bare(effect_id)
        }
    }

    /// An effect carrying text.
    pub fn text(effect_id: i64, text: &str) -> Self {
        Self {
            text: Some(text.to_owned()),
            ..Self::bare(effect_id)
        }
    }

    /// An effect with nothing in it yet (the caller fills what it reads).
    pub fn empty(effect_id: i64) -> Self {
        Self::bare(effect_id)
    }
}
