"""Message names and field numbers of the Dofus protocol: constants only."""

# Lot price response: message name and field numbers (see docs/protocol-notes.md).
LOT_RESPONSE_TYPE = "jzs"
LOT_DETAIL_FIELD = 1
LOT_ITEM_FIELD = 1
LOT_PRICES_FIELD = 2
LOT_FALLBACK_ITEM_FIELD = 3

# Market statistics response: message name and field numbers (see docs/protocol-notes.md).
STATS_RESPONSE_TYPE = "ire"
STATS_HOURLY_POINTS_FIELD = 1
STATS_DAILY_POINTS_FIELD = 3

# Fields of one statistics point (see docs/protocol-notes.md).
POINT_PRICE_FIELD = 1
POINT_ITEM_FIELD = 2
POINT_TIMESTAMP_FIELD = 3
POINT_QUANTITY_FIELD = 4

# Recycling (see docs/protocol-notes.md, structure seen in two captures of 2026-11-11).
RECYCLING_ADD_TYPE = "kch"  # server -> client: an item was added to the window
RECYCLING_UPDATE_TYPE = "kdr"  # server -> client: same shape, the new TOTAL quantity of an entry
RECYCLING_ADD_ENTRY_FIELD = 3
RECYCLING_ENTRY_FIELD = 1  # inside field 3
RECYCLING_QUANTITY_FIELD = 3
RECYCLING_ITEM_FIELD = 4  # DofusDB item id
RECYCLING_INSTANCE_FIELD = 5  # the stack the item comes from
RECYCLING_CLEAR_TYPE = "kiq"  # client -> server: the window is closed (it forgets its items)
RECYCLING_REQUEST_TYPE = "kba"  # client -> server: the player clicked Recycler
RECYCLING_RESULT_TYPE = "kdd"  # server -> client: the result
RECYCLING_NUGGETS_FIELD = 3  # nuggets obtained; absent when the result is 0
