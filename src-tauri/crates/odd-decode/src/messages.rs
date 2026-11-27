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
/// Server to client: the tax collectors of greatest value, both tabs.
pub const PERCEPTEURS_RESPONSE: &str = "hht";
/// Server to client: the player entered a map (lists the actors on it, collectors included).
pub const MAP_ENTRY: &str = "jnj";
/// Server to client: the player opened the dialog of an entity of the map.
pub const DIALOG_OPENED: &str = "ilx";
/// Server to client: the dialog of a tax collector.
pub const PERCEPTEUR_SHEET: &str = "iku";

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

/// Fields of the tax collectors window.
pub(crate) mod percepteurs {
    pub(crate) const CLASSIC_LINE: u32 = 1;
    pub(crate) const DUNGEON_LINE: u32 = 2;
    pub(crate) const LINE_VALUE_BOX: u32 = 1;
    pub(crate) const VALUE_BOX_INNER: u32 = 2;
    pub(crate) const VALUE: u32 = 3;
    pub(crate) const LINE_POSITION: u32 = 2;
    pub(crate) const POSITION_Y: u32 = 1;
    pub(crate) const POSITION_X: u32 = 3;
    pub(crate) const LINE_OWNER: u32 = 8;
    pub(crate) const LINE_SUB_AREA: u32 = 9;
    pub(crate) const LINE_ALLIANCE: u32 = 16;
    pub(crate) const ALLIANCE_TAG: u32 = 4;
    pub(crate) const ALLIANCE_NAME: u32 = 6;
}

/// Fields of the map entry, of the dialog opening and of the tax collector dialog.
pub(crate) mod roaming {
    pub(crate) const MAP_ID: u32 = 10;
    pub(crate) const MAP_SUB_AREA: u32 = 12;
    pub(crate) const MAP_ACTOR: u32 = 3;
    pub(crate) const ACTOR_ENTITY: u32 = 1;
    pub(crate) const ACTOR_POSITION: u32 = 2;
    pub(crate) const ACTOR_BODY: u32 = 3;
    pub(crate) const BODY_KIND: u32 = 1;
    pub(crate) const KIND_COLLECTOR: u32 = 7;
    pub(crate) const COLLECTOR_DATA: u32 = 2;
    pub(crate) const POSITION_CELL: u32 = 3;
    pub(crate) const POSITION_DIRECTION: u32 = 4;
    pub(crate) const DATA_ALLIANCE: u32 = 1;
    pub(crate) const DATA_NAME_FIRST: u32 = 3;
    pub(crate) const DATA_NAME_SECOND: u32 = 5;
    pub(crate) const ALLIANCE_EMBLEM: u32 = 3;
    pub(crate) const ALLIANCE_TAG: u32 = 4;
    pub(crate) const ALLIANCE_NAME: u32 = 6;
    pub(crate) const OPENED_MAP: u32 = 3;
    pub(crate) const OPENED_ENTITY: u32 = 5;
    pub(crate) const SHEET_ALLIANCE_COLLECTORS: u32 = 1;
    pub(crate) const SHEET_ALLIANCE: u32 = 2;
    pub(crate) const SHEET_POD_CAPACITY: u32 = 3;
    pub(crate) const SHEET_PROSPECTING: u32 = 4;
    pub(crate) const SHEET_PODS: u32 = 5;
    pub(crate) const SHEET_VALUE: u32 = 6;
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
