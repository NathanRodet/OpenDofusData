"""Builders of the item-window messages (recycling and breaking window), shaped like real captures."""

from opendofusdata.framing import Envelope
from tests.envelopes import bytes_field, int_field

OS_OF_CHAFER, TRUCHTINE_EYE, BOO_MUD, INVISIBLE_CLOTH = 310, 15073, 417, 2278
OS_STACK, EYE_STACK, MUD_STACK, CLOTH_STACK = 4854825, 5776723, 3376856, 5165041
CONSTANT_FLAG = 63


def added(quantity: int, item: int, stack: int) -> Envelope:
    entry = int_field(3, quantity) + int_field(4, item) + int_field(5, stack)
    return Envelope("kch", bytes_field(3, bytes_field(1, entry) + int_field(4, CONSTANT_FLAG)))


def updated(total: int, item: int, stack: int) -> Envelope:
    """The server's new total for an entry whose quantity was changed (same shape as an addition)."""
    entry = int_field(3, total) + int_field(4, item) + int_field(5, stack)
    return Envelope("kdr", bytes_field(3, bytes_field(1, entry) + int_field(4, CONSTANT_FLAG)))


def request(counter: int = 1) -> Envelope:
    return Envelope("kba", int_field(1, counter) + int_field(2, 1))


def result(nuggets: int) -> Envelope:
    return Envelope("kdd", int_field(3, nuggets) if nuggets else b"")


def cleared() -> Envelope:
    return Envelope("kiq", b"")
