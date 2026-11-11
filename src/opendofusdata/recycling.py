"""Recycling tracker: builds one event per recycling from the window messages (pure logic)."""

import logging

from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    RECYCLING_ADD_ENTRY_FIELD,
    RECYCLING_ADD_TYPE,
    RECYCLING_CLEAR_TYPE,
    RECYCLING_ENTRY_FIELD,
    RECYCLING_INSTANCE_FIELD,
    RECYCLING_ITEM_FIELD,
    RECYCLING_NUGGETS_FIELD,
    RECYCLING_QUANTITY_FIELD,
    RECYCLING_REQUEST_TYPE,
    RECYCLING_RESULT_TYPE,
    RECYCLING_UPDATE_TYPE,
)
from opendofusdata.protobuf import (
    WIRE_TYPE_LENGTH_DELIMITED,
    WIRE_TYPE_VARINT,
    DecodeError,
    decode_fields,
    first_field,
)
from opendofusdata.records import RecyclingEvent

logger = logging.getLogger(__name__)

NO_NUGGETS = 0
WindowEntry = tuple[int, int]


def _varint(fields: list, number: int) -> int | None:
    value = first_field(fields, number, WIRE_TYPE_VARINT)
    return value if isinstance(value, int) else None


def _message(fields: list, number: int) -> list | None:
    value = first_field(fields, number, WIRE_TYPE_LENGTH_DELIMITED)
    return decode_fields(value) if isinstance(value, bytes) else None


def _read_added_entry(payload: bytes) -> tuple[int, WindowEntry] | None:
    """(stack id, (item id, quantity)) from an item-added message, None when incomplete."""
    outer = _message(decode_fields(payload), RECYCLING_ADD_ENTRY_FIELD)
    entry = _message(outer, RECYCLING_ENTRY_FIELD) if outer is not None else None
    if entry is None:
        return None
    stack = _varint(entry, RECYCLING_INSTANCE_FIELD)
    item = _varint(entry, RECYCLING_ITEM_FIELD)
    quantity = _varint(entry, RECYCLING_QUANTITY_FIELD)
    if stack is None or not item or not quantity:
        return None
    return stack, (item, quantity)


class RecyclingTracker:
    """Follows the recycling window: items added or updated, the request, then the result."""

    def __init__(self, server: str) -> None:
        self._server = server
        self._window: dict[int, WindowEntry] = {}
        self._requested = False

    def feed(self, envelope: Envelope, from_server: bool, captured_at: str) -> RecyclingEvent | None:
        """Update the window state; return the event when a result completes a recycling."""
        try:
            return self._handle(envelope, from_server, captured_at)
        except DecodeError as error:
            logger.warning("unreadable %s message: %s", envelope.type_name, error)
            return None

    def _handle(self, envelope: Envelope, from_server: bool, captured_at: str) -> RecyclingEvent | None:
        kind = envelope.type_name
        if from_server and kind in (RECYCLING_ADD_TYPE, RECYCLING_UPDATE_TYPE):
            self._add(envelope.payload)
        elif not from_server and kind == RECYCLING_CLEAR_TYPE:
            self._reset()
        elif not from_server and kind == RECYCLING_REQUEST_TYPE:
            self._requested = bool(self._window)
        elif from_server and kind == RECYCLING_RESULT_TYPE:
            return self._complete(envelope.payload, captured_at)
        return None

    def _add(self, payload: bytes) -> None:
        added = _read_added_entry(payload)
        if added is not None:
            self._window[added[0]] = added[1]

    def _reset(self) -> None:
        self._window.clear()
        self._requested = False

    def _complete(self, payload: bytes, captured_at: str) -> RecyclingEvent | None:
        if not self._requested:
            return None
        nuggets = _varint(decode_fields(payload), RECYCLING_NUGGETS_FIELD) or NO_NUGGETS
        event = RecyclingEvent(self._server, tuple(self._window.values()), nuggets, captured_at)
        self._reset()
        return event
