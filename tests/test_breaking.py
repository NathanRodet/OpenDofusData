"""Tests of the breaking (concassage) tracker: one record per destroyed object, built on real captures."""

import struct

from opendofusdata.breaking import BreakingTracker
from opendofusdata.framing import Envelope
from opendofusdata.records import BrokenItem
from tests.envelopes import bytes_field, int_field, varint
from tests.test_recycling import added, cleared, request, result, updated

SERVER = "Brial"
MOMENT = "2026-11-11T19:27:56Z"
LISSEUR, VOLKORNE_ORCHID, VOLKORNE_EBONY = 942, 33199, 33166
GA_PA, INE, FO, AGE = 1557, 1522, 1519, 1524
LISSEUR_STACK, ORCHID_STACK, EBONY_STACK = 6249806, 5206480, 4634477
HALF_BITS, FIFTY_THREE_BITS = 1056964608, 1057528607
FIFTY_THREE = struct.unpack("<f", struct.pack("<I", FIFTY_THREE_BITS))[0]


def fixed32(number: int, bits: int) -> bytes:
    return varint((number << 3) | 5) + struct.pack("<I", bits)


def outcome(stack: int, runes: tuple[tuple[int, int], ...], bits: int = HALF_BITS) -> bytes:
    body = fixed32(1, bits) + fixed32(2, bits) + int_field(3, stack)
    body += b"".join(bytes_field(4, int_field(1, quantity) + int_field(2, rune)) for quantity, rune in runes)
    return bytes_field(1, body)


def broken(*outcomes: bytes) -> Envelope:
    return Envelope("kag", b"".join(outcomes))


def break_request(count: int = 1) -> Envelope:
    return Envelope("jxy", int_field(1, count) + int_field(3, 1))


def float_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def item(item_id: int, quantity: int, coefficient: float, runes: tuple[tuple[int, int], ...]) -> BrokenItem:
    return BrokenItem(SERVER, item_id, quantity, coefficient, runes, MOMENT)


def play(tracker: BreakingTracker, *steps: tuple[Envelope, bool]) -> list[list[BrokenItem]]:
    return [tracker.feed(envelope, from_server, MOMENT) for envelope, from_server in steps]


def tracker() -> BreakingTracker:
    return BreakingTracker(SERVER)


def test_the_real_concassage_of_two_volkornes_gives_one_record_per_object() -> None:
    outcomes = play(tracker(),
                    (added(1, VOLKORNE_ORCHID, ORCHID_STACK), True), (added(1, VOLKORNE_EBONY, EBONY_STACK), True),
                    (break_request(2), False),
                    (broken(outcome(ORCHID_STACK, ((1, GA_PA), (38, INE))), outcome(EBONY_STACK, ((38, AGE),))), True))
    assert outcomes[:-1] == [[]] * 3
    assert outcomes[-1] == [item(VOLKORNE_ORCHID, 1, 0.5, ((GA_PA, 1), (INE, 38))),
                            item(VOLKORNE_EBONY, 1, 0.5, ((AGE, 38),))]


def test_an_item_that_gives_no_rune_is_still_recorded_with_its_coefficient() -> None:
    outcomes = play(tracker(), (added(1, LISSEUR, LISSEUR_STACK), True), (break_request(1), False),
                    (broken(outcome(LISSEUR_STACK, (), FIFTY_THREE_BITS)), True))
    assert outcomes[-1] == [item(LISSEUR, 1, FIFTY_THREE, ())]
    assert round(outcomes[-1][0].coefficient * 100) == 53


def test_the_quantity_comes_from_the_window_and_follows_updates() -> None:
    outcomes = play(tracker(), (added(5, LISSEUR, LISSEUR_STACK), True), (updated(3, LISSEUR, LISSEUR_STACK), True),
                    (broken(outcome(LISSEUR_STACK, ((2, FO),))), True))
    assert outcomes[-1] == [item(LISSEUR, 3, 0.5, ((FO, 2),))]


def test_a_result_for_an_unknown_object_is_skipped_but_known_ones_are_kept() -> None:
    outcomes = play(tracker(), (added(1, LISSEUR, LISSEUR_STACK), True),
                    (broken(outcome(999, ((1, FO),)), outcome(LISSEUR_STACK, ())), True))
    assert outcomes[-1] == [item(LISSEUR, 1, 0.5, ())]


def test_a_result_with_no_known_object_gives_nothing() -> None:
    assert play(tracker(), (broken(outcome(999, ((1, FO),))), True)) == [[]]


def test_the_window_is_empty_after_a_result() -> None:
    breaking = tracker()
    play(breaking, (added(1, LISSEUR, LISSEUR_STACK), True), (broken(outcome(LISSEUR_STACK, ())), True))
    assert play(breaking, (broken(outcome(LISSEUR_STACK, ())), True)) == [[]]


def test_closing_the_window_forgets_its_objects() -> None:
    outcomes = play(tracker(), (added(1, LISSEUR, LISSEUR_STACK), True), (cleared(), False),
                    (broken(outcome(LISSEUR_STACK, ())), True))
    assert outcomes[-1] == []


def test_a_recycling_result_empties_the_window_so_its_objects_are_not_broken_later() -> None:
    outcomes = play(tracker(), (added(1, LISSEUR, LISSEUR_STACK), True), (request(), False), (result(0), True),
                    (broken(outcome(LISSEUR_STACK, ())), True))
    assert outcomes[-1] == []


def test_messages_in_the_wrong_direction_are_ignored() -> None:
    outcomes = play(tracker(), (added(1, LISSEUR, LISSEUR_STACK), True),
                    (broken(outcome(LISSEUR_STACK, ())), False))
    assert outcomes[-1] == []


def test_unreadable_payloads_are_ignored_without_raising() -> None:
    assert play(tracker(), (Envelope("kag", b"\xff\xff\xff"), True), (Envelope("kag", b"\x0a\x05\x08"), True)) == [[], []]


def test_unrelated_messages_do_nothing() -> None:
    assert play(tracker(), (Envelope("jzs", b""), True), (break_request(), False)) == [[], []]


SANDALS, SANDAL_STACKS = 8228, (6493110, 5121498, 4907810)
SANDAL_COEFFICIENT_BITS = (1052107770, 1052104412, 1052101055)  # seen in game: all shown as 36 %
SANDAL_RUNES = (2, 2, 1)


def test_the_real_concassage_of_three_identical_sandals_keeps_each_object_and_its_own_coefficient() -> None:
    steps = [(added(1, SANDALS, stack), True) for stack in SANDAL_STACKS]
    steps.append((break_request(3), False))
    steps.append((broken(*(outcome(stack, ((quantity, AGE),), bits) for stack, quantity, bits
                           in zip(SANDAL_STACKS, SANDAL_RUNES, SANDAL_COEFFICIENT_BITS))), True))
    records = play(tracker(), *steps)[-1]
    assert [record.item_id for record in records] == [SANDALS] * 3
    assert [record.runes for record in records] == [((AGE, 2),), ((AGE, 2),), ((AGE, 1),)]
    assert [round(record.coefficient * 100) for record in records] == [36, 36, 36]
    assert records[0].coefficient > records[1].coefficient > records[2].coefficient


MIXED_SHOWN_PERCENT = (44, 26, 98, 16, 16, 35)
MIXED_COEFFICIENTS = (0.43649, 0.26309, 0.97543, 0.15774, 0.15771, 0.35488)  # seen in game


def test_six_objects_of_the_real_capture_round_to_the_percentages_the_game_showed() -> None:
    stacks = tuple(range(1000, 1006))
    steps = [(added(1, 900 + index, stack), True) for index, stack in enumerate(stacks)]
    steps.append((updated(2, 905, stacks[5]), True))  # the last object is a stack of two
    steps.append((broken(*(outcome(stack, ((1, AGE),), float_bits(coefficient))
                           for stack, coefficient in zip(stacks, MIXED_COEFFICIENTS))), True))
    records = play(tracker(), *steps)[-1]
    assert [round(record.coefficient * 100) for record in records] == list(MIXED_SHOWN_PERCENT)
    assert [record.quantity for record in records] == [1, 1, 1, 1, 1, 2]
