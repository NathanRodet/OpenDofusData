//! Payloads `hdv.stats` and `hdv.category`: market statistics and what is for sale in a type.

use serde::{Deserialize, Serialize};

/// Statistics of one period, computed from the points the game sends.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Period {
    /// Number of items sold.
    pub sold: i64,
    /// Median price, weighted by the quantities sold.
    pub median: i64,
    /// Mean price, weighted by the quantities sold.
    pub mean: f64,
}

/// The three periods of the market graph.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Periods {
    /// The last 24 hours.
    #[serde(rename = "24h")]
    pub h24: Period,
    /// The last 7 days.
    #[serde(rename = "7d")]
    pub d7: Period,
    /// The last 30 days.
    #[serde(rename = "30d")]
    pub d30: Period,
}

/// One point of the graph.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Point {
    /// Timestamp exactly as the game wrote it (ISO 8601, UTC).
    pub at: String,
    /// Price at that point.
    pub price: i64,
    /// Quantity sold.
    pub quantity: i64,
}

/// The points of the 24 hour and 30 day curves.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Points {
    /// One point per hour with sales.
    pub hourly: Vec<Point>,
    /// One point per day.
    pub daily: Vec<Point>,
}

/// The market graph of an item.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HdvStats {
    /// The item.
    pub item_id: i64,
    /// Timestamp of the last purchase, as the game wrote it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_purchase_at: Option<String>,
    /// Statistics of the three periods.
    pub periods: Periods,
    /// Every point of the graph.
    pub points: Points,
}

/// The items of a type that have at least one offer.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HdvCategory {
    /// The game's item type id.
    pub item_type_id: i64,
    /// Items of that type currently for sale.
    pub item_ids: Vec<i64>,
}
