//! Names and field numbers of the game messages.
//!
//! The short type names (`jzs`, `kch`...) change with each version of the game: this is the only file
//! to update when they do. Field numbers come from captures, see docs/field-inventory.md.

/// Client to server: opens (field 2 set) or closes (no field 2) the sheet of an item.
pub const LOT_REQUEST: &str = "kcy";
/// Server to client: the offers of an item.
pub const LOT_RESPONSE: &str = "jzs";
/// Client to server: asks for the market graph of an item.
pub const STATS_REQUEST: &str = "iqp";
/// Server to client: the market graph of an item.
pub const STATS_RESPONSE: &str = "ire";
/// Server to client: the items of a type that are for sale.
pub const CATEGORY_RESPONSE: &str = "kbj";
/// Server to client: an item put in the Concasseur window.
pub const WINDOW_ADD: &str = "kch";
/// Server to client: the new total of an item already in the window (same shape as `WINDOW_ADD`).
pub const WINDOW_UPDATE: &str = "kdr";
/// Client to server: the window is closed.
pub const WINDOW_CLOSE: &str = "kiq";
/// Client to server: break what is in the window (field 2 is the chosen focus).
pub const BREAK_REQUEST: &str = "jxy";
/// Server to client: the result of a breaking, one entry per item.
pub const BREAK_RESULT: &str = "kag";

/// Sizes of the lots of a stackable resource, in the order of the prices.
pub const LOT_SIZES: [u32; 4] = [1, 10, 100, 1000];

/// Fields of the lot request and response.
pub(crate) mod lot {
    pub(crate) const REQUEST_ITEM: u32 = 1;
    pub(crate) const REQUEST_OPEN: u32 = 2;
    pub(crate) const ENTRY: u32 = 1;
    pub(crate) const ENTRY_ITEM: u32 = 1;
    pub(crate) const ENTRY_PRICES: u32 = 2;
    pub(crate) const ENTRY_OFFER: u32 = 3;
    pub(crate) const ENTRY_TYPE: u32 = 4;
    pub(crate) const ENTRY_EFFECT: u32 = 5;
    pub(crate) const RESPONSE_TYPE: u32 = 2;
    pub(crate) const RESPONSE_ITEM: u32 = 3;
}

/// Fields of the market graph request and response.
pub(crate) mod stats {
    pub(crate) const REQUEST_ITEM: u32 = 1;
    pub(crate) const HOURLY_POINT: u32 = 1;
    pub(crate) const DAILY_POINT: u32 = 3;
    pub(crate) const POINT_PRICE: u32 = 1;
    pub(crate) const POINT_ITEM: u32 = 2;
    pub(crate) const POINT_AT: u32 = 3;
    pub(crate) const POINT_QUANTITY: u32 = 4;
}

/// Fields of the category answer.
pub(crate) mod category {
    pub(crate) const ITEM_IDS: u32 = 1;
    pub(crate) const ITEM_TYPE: u32 = 2;
}

/// Fields of the Concasseur messages.
pub(crate) mod breaking {
    pub(crate) const WINDOW_BODY: u32 = 3;
    pub(crate) const WINDOW_OBJECT: u32 = 1;
    pub(crate) const OBJECT_QUANTITY: u32 = 3;
    pub(crate) const OBJECT_ITEM: u32 = 4;
    pub(crate) const OBJECT_INSTANCE: u32 = 5;
    pub(crate) const OBJECT_EFFECT: u32 = 7;
    pub(crate) const REQUEST_FOCUS: u32 = 2;
    pub(crate) const RESULT_ENTRY: u32 = 1;
    pub(crate) const ENTRY_COEFFICIENT: u32 = 1;
    pub(crate) const ENTRY_COEFFICIENT_ALT: u32 = 2;
    pub(crate) const ENTRY_INSTANCE: u32 = 3;
    pub(crate) const ENTRY_RUNE: u32 = 4;
    pub(crate) const RUNE_QUANTITY: u32 = 1;
    pub(crate) const RUNE_ITEM: u32 = 2;
}
