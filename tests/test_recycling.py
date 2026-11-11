"""Tests of the recycling tracker, built on the message structure seen in real captures."""

from opendofusdata.framing import Envelope
from opendofusdata.recycling import RecyclingTracker
from opendofusdata.records import RecyclingEvent
from tests.envelopes import bytes_field, int_field

SERVER = "Brial"
MOMENT = "2026-11-11T19:18:30Z"
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


def play(tracker: RecyclingTracker, *steps: tuple[Envelope, bool]) -> list[RecyclingEvent | None]:
    return [tracker.feed(envelope, from_server, MOMENT) for envelope, from_server in steps]


def tracker() -> RecyclingTracker:
    return RecyclingTracker(SERVER)


def test_a_recycling_of_four_items_gives_one_event_with_the_nuggets() -> None:
    outcome = play(tracker(),
                   (added(100, OS_OF_CHAFER, OS_STACK), True), (added(10, TRUCHTINE_EYE, EYE_STACK), True),
                   (added(10, BOO_MUD, MUD_STACK), True), (added(10, INVISIBLE_CLOTH, CLOTH_STACK), True),
                   (request(4), False), (result(2), True))
    assert outcome[:-1] == [None] * 5
    assert outcome[-1] == RecyclingEvent(
        SERVER, ((OS_OF_CHAFER, 100), (TRUCHTINE_EYE, 10), (BOO_MUD, 10), (INVISIBLE_CLOTH, 10)), 2, MOMENT)


def test_an_empty_result_message_means_zero_nuggets() -> None:
    outcome = play(tracker(), (added(1, OS_OF_CHAFER, OS_STACK), True), (request(1), False), (result(0), True))
    assert outcome[-1] == RecyclingEvent(SERVER, ((OS_OF_CHAFER, 1),), 0, MOMENT)


def test_adding_the_same_stack_again_replaces_its_quantity() -> None:
    outcome = play(tracker(), (added(1, OS_OF_CHAFER, OS_STACK), True), (added(1000, OS_OF_CHAFER, OS_STACK), True),
                   (request(), False), (result(3), True))
    assert outcome[-1].items == ((OS_OF_CHAFER, 1000),)
    assert outcome[-1].nuggets == 3


def test_a_quantity_change_keeps_the_latest_total() -> None:
    """Real sequence of 2026-11-11: 100, minus one three times, then 95 more (total 190)."""
    outcome = play(tracker(), (added(100, OS_OF_CHAFER, OS_STACK), True),
                   (updated(99, OS_OF_CHAFER, OS_STACK), True), (updated(98, OS_OF_CHAFER, OS_STACK), True),
                   (updated(97, OS_OF_CHAFER, OS_STACK), True), (updated(190, OS_OF_CHAFER, OS_STACK), True),
                   (request(7), False), (result(1), True))
    assert outcome[-1] == RecyclingEvent(SERVER, ((OS_OF_CHAFER, 190),), 1, MOMENT)


def test_a_quantity_change_only_touches_its_own_stack() -> None:
    outcome = play(tracker(), (added(10, OS_OF_CHAFER, OS_STACK), True), (added(5, TRUCHTINE_EYE, EYE_STACK), True),
                   (updated(8, OS_OF_CHAFER, OS_STACK), True), (request(), False), (result(0), True))
    assert outcome[-1].items == ((OS_OF_CHAFER, 8), (TRUCHTINE_EYE, 5))


def test_closing_the_window_sends_several_clears_and_forgets_everything() -> None:
    outcome = play(tracker(), (added(100, OS_OF_CHAFER, OS_STACK), True), (cleared(), False), (cleared(), False),
                   (request(), False), (result(2), True))
    assert outcome[-1] is None


def test_clearing_the_window_forgets_what_was_added() -> None:
    outcome = play(tracker(), (added(100, BOO_MUD, MUD_STACK), True), (cleared(), False),
                   (added(100, OS_OF_CHAFER, OS_STACK), True), (request(), False), (result(1), True))
    assert outcome[-1].items == ((OS_OF_CHAFER, 100),)


def test_the_window_is_empty_after_a_result() -> None:
    steps = [(added(1, OS_OF_CHAFER, OS_STACK), True), (request(), False), (result(0), True)]
    recycling = tracker()
    play(recycling, *steps)
    assert play(recycling, (request(), False), (result(0), True)) == [None, None]


def test_a_result_without_a_request_is_ignored() -> None:
    assert play(tracker(), (added(1, OS_OF_CHAFER, OS_STACK), True), (result(2), True)) == [None, None]


def test_a_request_with_an_empty_window_gives_no_event() -> None:
    assert play(tracker(), (request(), False), (result(2), True)) == [None, None]


def test_messages_in_the_wrong_direction_are_ignored() -> None:
    outcome = play(tracker(), (added(1, OS_OF_CHAFER, OS_STACK), False), (request(), True), (result(2), False))
    assert outcome == [None, None, None]


def test_two_recyclings_in_a_row_give_two_events() -> None:
    recycling = tracker()
    first = play(recycling, (added(1, OS_OF_CHAFER, OS_STACK), True), (request(1), False), (result(0), True))
    second = play(recycling, (added(1000, OS_OF_CHAFER, OS_STACK), True), (request(2), False), (result(3), True))
    assert (first[-1].nuggets, second[-1].nuggets) == (0, 3)
    assert second[-1].items == ((OS_OF_CHAFER, 1000),)


def test_unreadable_payloads_are_ignored_without_raising() -> None:
    broken = Envelope("kch", b"\xff\xff\xff")
    assert play(tracker(), (broken, True), (Envelope("kdd", b"\x80"), True)) == [None, None]


def test_entries_without_item_id_or_quantity_are_skipped() -> None:
    no_item = Envelope("kch", bytes_field(3, bytes_field(1, int_field(3, 5) + int_field(5, OS_STACK))))
    no_quantity = Envelope("kch", bytes_field(3, bytes_field(1, int_field(4, OS_OF_CHAFER) + int_field(5, OS_STACK))))
    outcome = play(tracker(), (no_item, True), (no_quantity, True), (request(), False), (result(1), True))
    assert outcome == [None, None, None, None]


def test_unrelated_messages_do_nothing() -> None:
    assert play(tracker(), (Envelope("jzs", b""), True), (Envelope("knb", b"\x08\x01"), True)) == [None, None]
