"""Recycling tracker: builds one event per recycling from the window messages (pure logic)."""

import logging
from collections.abc import Callable

from opendofusdata.crafting_window import CraftingWindow, read_varint_field
from opendofusdata.framing import Envelope
from opendofusdata.messages import (
    BREAKING_RESULT_TYPE,
    RECYCLING_NUGGETS_FIELD,
    RECYCLING_REQUEST_TYPE,
    RECYCLING_RESULT_TYPE,
)
from opendofusdata.protobuf import DecodeError, decode_fields
from opendofusdata.records import RecyclingEvent

logger = logging.getLogger(__name__)

NO_NUGGETS = 0
# The "Personnage" column of the game: yield shown = quantity x DofusDB recyclingNuggets x this factor
# (0.6 on every capture of 2026-11-11; whether it depends on the character is not known).
PERSONAL_FACTOR = 0.6


def expected_nuggets(items: tuple[tuple[int, int], ...], rate_of: Callable[[int], float | None]) -> float | None:
    """The yield the game announces for these items; None when there is none or a rate is unknown."""
    total = 0.0
    for item_id, quantity in items:
        rate = rate_of(item_id)
        if rate is None:
            return None
        total += rate * quantity
    return total * PERSONAL_FACTOR if items else None


class RecyclingTracker:
    """Follows the recycling window: items added or updated, the request, then the result."""

    def __init__(self, server: str) -> None:
        self._server = server
        self._window = CraftingWindow()
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
        if not from_server and kind == RECYCLING_REQUEST_TYPE:
            self._requested = bool(self._window.entries)
        elif from_server and kind == RECYCLING_RESULT_TYPE:
            return self._complete(envelope.payload, captured_at)
        elif from_server and kind == BREAKING_RESULT_TYPE:
            self._reset()  # the window was used for a breaking: its items are gone
        else:
            self._window.handle(envelope, from_server)
            self._requested = self._requested and bool(self._window.entries)
        return None

    def _reset(self) -> None:
        self._window.reset()
        self._requested = False

    def _complete(self, payload: bytes, captured_at: str) -> RecyclingEvent | None:
        if not self._requested:
            return None
        nuggets = read_varint_field(decode_fields(payload), RECYCLING_NUGGETS_FIELD) or NO_NUGGETS
        event = RecyclingEvent(self._server, self._window.items(), nuggets, captured_at)
        self._reset()
        return event
