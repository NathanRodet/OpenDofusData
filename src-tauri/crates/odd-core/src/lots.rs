//! Payload of `hdv.lots`: what an item sells for at the auction house.

use serde::{Deserialize, Serialize};

use crate::effect::Effect;
use crate::unmapped::Unmapped;

/// A lot of a stackable resource: `size` items for `price` kamas in total.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Lot {
    /// Number of items in the lot (1, 10, 100 or 1000).
    pub size: u32,
    /// Price of the whole lot.
    pub price: i64,
}

/// One offer of a unique item (equipment, mount), with all its effects.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Offer {
    /// The game's offer id.
    pub offer_id: i64,
    /// Price in kamas.
    pub price: i64,
    /// Effects of this exact item.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub effects: Vec<Effect>,
    /// Fields of the offer not understood yet.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub unmapped: Vec<Unmapped>,
}

/// The two shapes of an item listing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Listing {
    /// A stackable resource: one price per lot size.
    Lots {
        /// The lot sizes that exist.
        lots: Vec<Lot>,
    },
    /// A unique item: every offer. An empty list means no offer at that moment.
    Offers {
        /// The offers.
        offers: Vec<Offer>,
    },
}

/// Everything the auction house shows when an item sheet is opened.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HdvLots {
    /// The item.
    pub item_id: i64,
    /// The game's item type id (47 for bones, 11 for boots, 331 for mounts...).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub item_type_id: Option<i64>,
    /// Lots or offers.
    #[serde(flatten)]
    pub listing: Listing,
}

impl HdvLots {
    /// A stackable resource listing.
    pub fn resource(item_id: i64, item_type_id: Option<i64>, lots: Vec<Lot>) -> Self {
        Self {
            item_id,
            item_type_id,
            listing: Listing::Lots { lots },
        }
    }

    /// A unique item listing.
    pub fn unique(item_id: i64, item_type_id: Option<i64>, offers: Vec<Offer>) -> Self {
        Self {
            item_id,
            item_type_id,
            listing: Listing::Offers { offers },
        }
    }
}
