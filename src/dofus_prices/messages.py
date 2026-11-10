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
