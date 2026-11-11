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

# Pets (see docs/protocol-notes.md, captures of 2026-11-11). Objects are identified by an
# instance id that changes with each connection; the inventory maps it to the DofusDB item id.
INVENTORY_LIST_TYPE = "irl"  # server -> client at login: every object of the inventory
INVENTORY_ENTRY_FIELD = 2  # repeated: {1: object, 4: container}
INVENTORY_UPDATE_TYPE = "iqx"  # server -> client: object(s) added or changed after login, same entry shape
OBJECT_FIELD = 1
OBJECT_QUANTITY_FIELD = 3
OBJECT_ITEM_FIELD = 4  # DofusDB item id
OBJECT_INSTANCE_FIELD = 5
OBJECT_EFFECTS_FIELD = 7  # repeated effects
EFFECT_ID_FIELD = 10
EFFECT_VALUE_FIELD = 5  # plain value (prospection)
EFFECT_DETAIL_FIELD = 9  # {2: maximum, 4: current}
EFFECT_DETAIL_MAX_FIELD = 2
EFFECT_DETAIL_CURRENT_FIELD = 4
EFFECT_PROSPECTION = 176
EFFECT_PET_LEVEL = 2821
EFFECT_PET_EXPERIENCE = 2819
PET_FEED_TYPE = "irb"  # client -> server: {2: pet instance, 3: repeated {1: quantity, 3: stack instance}}
PET_FEED_PET_FIELD = 2
PET_FEED_RESOURCE_FIELD = 3
PET_FEED_QUANTITY_FIELD = 1
PET_FEED_STACK_FIELD = 3
PET_UPDATE_TYPE = "iqy"  # server -> client: the pet after the upgrade, {1: {1: object, 4: container}}
PET_UPDATE_ENTRY_FIELD = 1

# Breaking at the Concasseur (see docs/protocol-notes.md). The window uses the same add, update
# and close messages as recycling; the result lists each destroyed object with its coefficient.
BREAKING_RESULT_TYPE = "kag"  # server -> client: {1: repeated outcome}
BREAKING_RESULT_ENTRY_FIELD = 1
BREAKING_COEFFICIENT_FIELD = 1  # 32-bit float, 0.5 = 50 %
BREAKING_OBJECT_FIELD = 3  # instance id of the destroyed object
BREAKING_RUNE_FIELD = 4  # repeated {1: quantity, 2: rune item id}
BREAKING_RUNE_QUANTITY_FIELD = 1
BREAKING_RUNE_ITEM_FIELD = 2
