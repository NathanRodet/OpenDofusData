"""Breaking tracker: one event per breaking (concassage) with the coefficient and runes of each item."""

import logging
import struct

from opendofusdata.crafting_window import CraftingWindow, read_varint_field
from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    BREAKING_COEFFICIENT_FIELD,
    BREAKING_OBJECT_FIELD,
    BREAKING_RESULT_ENTRY_FIELD,
    BREAKING_RESULT_TYPE,
    BREAKING_RUNE_FIELD,
    BREAKING_RUNE_ITEM_FIELD,
    BREAKING_RUNE_QUANTITY_FIELD,
    RECYCLING_RESULT_TYPE,
)
from opendofusdata.protobuf import (
    WIRE_TYPE_FIXED32,
    WIRE_TYPE_LENGTH_DELIMITED,
    DecodeError,
    Field,
    decode_fields,
    first_field,
)
from opendofusdata.records import BrokenItem

logger = logging.getLogger(__name__)

FLOAT32_FORMAT = "<f"
INTEGER32_FORMAT = "<I"


def _messages(fields: list[Field], number: int) -> list[list[Field]]:
    return [decode_fields(value) for field_number, wire_type, value in fields
            if field_number == number and wire_type == WIRE_TYPE_LENGTH_DELIMITED and isinstance(value, bytes)]


def _coefficient(fields: list[Field]) -> float | None:
    """The 32-bit float of the coefficient field (0.5 means 50 %)."""
    bits = first_field(fields, BREAKING_COEFFICIENT_FIELD, WIRE_TYPE_FIXED32)
    return struct.unpack(FLOAT32_FORMAT, struct.pack(INTEGER32_FORMAT, bits))[0] if isinstance(bits, int) else None


def _runes(outcome: list[Field]) -> tuple[tuple[int, int], ...]:
    runes = []
    for rune in _messages(outcome, BREAKING_RUNE_FIELD):
        item = read_varint_field(rune, BREAKING_RUNE_ITEM_FIELD)
        quantity = read_varint_field(rune, BREAKING_RUNE_QUANTITY_FIELD)
        if item and quantity:
            runes.append((item, quantity))
    return tuple(runes)


class BreakingTracker:
    """Follows the window of the Concasseur and reads the result of each breaking."""

    def __init__(self, server: str) -> None:
        self._server = server
        self._window = CraftingWindow()

    def feed(self, envelope: Envelope, from_server: bool, captured_at: str) -> list[BrokenItem]:
        """Update the window state; return one record per object when a breaking result arrives."""
        try:
            return self._handle(envelope, from_server, captured_at)
        except DecodeError as error:
            logger.warning("unreadable %s message: %s", envelope.type_name, error)
            return []

    def _handle(self, envelope: Envelope, from_server: bool, captured_at: str) -> list[BrokenItem]:
        kind = envelope.type_name
        if from_server and kind == BREAKING_RESULT_TYPE:
            return self._complete(envelope.payload, captured_at)
        if from_server and kind == RECYCLING_RESULT_TYPE:
            self._window.reset()  # the window was used for a recycling: its items are gone
        else:
            self._window.handle(envelope, from_server)
        return []

    def _complete(self, payload: bytes, captured_at: str) -> list[BrokenItem]:
        items = []
        for outcome in _messages(decode_fields(payload), BREAKING_RESULT_ENTRY_FIELD):
            known = self._window.entries.get(read_varint_field(outcome, BREAKING_OBJECT_FIELD) or 0)
            coefficient = _coefficient(outcome)
            if known is not None and coefficient is not None:
                items.append(BrokenItem(self._server, known[0], known[1], coefficient, _runes(outcome), captured_at))
        self._window.reset()
        return items
