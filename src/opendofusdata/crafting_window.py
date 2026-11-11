"""State of the item window shared by recycling and breaking: items added, updated, window closed."""

from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    RECYCLING_ADD_ENTRY_FIELD,
    RECYCLING_ADD_TYPE,
    RECYCLING_CLEAR_TYPE,
    RECYCLING_ENTRY_FIELD,
    RECYCLING_INSTANCE_FIELD,
    RECYCLING_ITEM_FIELD,
    RECYCLING_QUANTITY_FIELD,
    RECYCLING_UPDATE_TYPE,
)
from opendofusdata.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    WIRE_TYPE_VARINT,
    decode_fields,
    first_field,
)

MAX_WINDOW_ENTRIES = 1_000  # the in-game limit is far lower (800 for the recycling window)
WindowEntry = tuple[int, int]  # (item id, quantity)


def read_varint_field(fields: list, number: int) -> int | None:
    """The first varint with this field number, or None."""
    value = first_field(fields, number, WIRE_TYPE_VARINT)
    return value if isinstance(value, int) else None


def read_message_field(fields: list, number: int) -> list | None:
    """The decoded first length-delimited message with this field number, or None."""
    value = first_field(fields, number, WIRE_TYPE_LENGTH_DELIMITED)
    return decode_fields(value) if isinstance(value, bytes) else None


def _read_added_entry(payload: bytes) -> tuple[int, WindowEntry] | None:
    """(stack id, (item id, quantity)) from an item-added or item-updated message."""
    outer = read_message_field(decode_fields(payload), RECYCLING_ADD_ENTRY_FIELD)
    entry = read_message_field(outer, RECYCLING_ENTRY_FIELD) if outer is not None else None
    if entry is None:
        return None
    stack = read_varint_field(entry, RECYCLING_INSTANCE_FIELD)
    item = read_varint_field(entry, RECYCLING_ITEM_FIELD)
    quantity = read_varint_field(entry, RECYCLING_QUANTITY_FIELD)
    if stack is None or not item or not quantity:
        return None
    return stack, (item, quantity)


class CraftingWindow:
    """The items currently in the window, by stack id (the server's latest quantity wins)."""

    def __init__(self) -> None:
        self.entries: dict[int, WindowEntry] = {}

    def handle(self, envelope: Envelope, from_server: bool) -> None:
        """Apply an item added/updated (server) or the window being closed (client)."""
        kind = envelope.type_name
        if from_server and kind in (RECYCLING_ADD_TYPE, RECYCLING_UPDATE_TYPE):
            added = _read_added_entry(envelope.payload)
            if added is not None and (added[0] in self.entries or len(self.entries) < MAX_WINDOW_ENTRIES):
                self.entries[added[0]] = added[1]
        elif not from_server and kind == RECYCLING_CLEAR_TYPE:
            self.reset()

    def reset(self) -> None:
        """Forget every item."""
        self.entries.clear()

    def items(self) -> tuple[WindowEntry, ...]:
        """(item id, quantity) of every item, in the order they were added."""
        return tuple(self.entries.values())
