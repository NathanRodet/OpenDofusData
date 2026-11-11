"""Tests of the pet tracker, built on the message structure seen in the captures of 2026-11-11."""

from opendofusdata.framing import Envelope
from opendofusdata.pets import PetTracker
from opendofusdata.records import PetFeeding, PetState
from tests.envelopes import bytes_field, int_field

SERVER = "Brial"
MOMENT = "2026-11-11T19:25:06Z"
BONE, EYE, NOMOON = 310, 15073, 6716
BONE_STACK, EYE_STACK, PET = 2668079, 5776723, 4409814
PROSPECTION, LEVEL, EXPERIENCE = 176, 2821, 2819
CONTAINER_FLAG = 63


def pet_entry(level: int = 32, experience: int = 257, prospection: int = 46, maximum: int = 286,
              uid: int = PET) -> bytes:
    effects = (bytes_field(7, int_field(5, prospection) + int_field(10, PROSPECTION))
               + bytes_field(7, bytes_field(9, int_field(1, 18) + int_field(4, level)) + int_field(10, LEVEL))
               + bytes_field(7, bytes_field(9, int_field(2, maximum) + int_field(4, experience))
                             + int_field(10, EXPERIENCE)))
    return int_field(3, 1) + int_field(4, NOMOON) + int_field(5, uid) + effects


def stack_entry(item: int, uid: int, quantity: int) -> bytes:
    return int_field(3, quantity) + int_field(4, item) + int_field(5, uid)


def inventory(*entries: bytes) -> Envelope:
    body = b"".join(bytes_field(2, bytes_field(1, entry) + int_field(4, CONTAINER_FLAG)) for entry in entries)
    return Envelope("irl", body + int_field(4, 1))


def feed(pet: int, *stacks: tuple[int, int]) -> Envelope:
    body = int_field(2, pet) + b"".join(bytes_field(3, int_field(1, quantity) + int_field(3, stack))
                                        for quantity, stack in stacks)
    return Envelope("irb", body)


def updated(entry: bytes) -> Envelope:
    return Envelope("iqy", bytes_field(1, bytes_field(1, entry) + int_field(4, CONTAINER_FLAG)))


def start() -> PetTracker:
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(stack_entry(BONE, BONE_STACK, 4787), stack_entry(EYE, EYE_STACK, 35), pet_entry()),
                 True, MOMENT)
    return tracker


def play(tracker: PetTracker, *steps: tuple[Envelope, bool]) -> list[PetFeeding | None]:
    return [tracker.feed(envelope, from_server, MOMENT) for envelope, from_server in steps]


def test_the_real_feeding_gives_the_resource_the_states_and_the_gain() -> None:
    outcome = play(start(), (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(experience=262)), True))
    assert outcome[0] is None
    assert outcome[1] == PetFeeding(
        SERVER, NOMOON, ((BONE, 100),), PetState(32, 257, 286, 46), PetState(32, 262, 286, 46), MOMENT)


def test_a_level_up_and_a_prospection_gain_are_in_the_after_state() -> None:
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(stack_entry(BONE, BONE_STACK, 6113), stack_entry(EYE, EYE_STACK, 37),
                           pet_entry(level=31, experience=240, prospection=45)), True, MOMENT)
    outcome = play(tracker, (feed(PET, (125, BONE_STACK), (2, EYE_STACK)), False),
                   (updated(pet_entry(level=32, experience=257, prospection=46)), True))
    assert outcome[1].resources == ((BONE, 125), (EYE, 2))
    assert outcome[1].before == PetState(31, 240, 286, 45)
    assert outcome[1].after == PetState(32, 257, 286, 46)


def test_the_next_feeding_starts_from_the_previous_after_state() -> None:
    tracker = start()
    play(tracker, (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(experience=262)), True))
    outcome = play(tracker, (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(experience=267)), True))
    assert outcome[1].before.experience == 262
    assert outcome[1].after.experience == 267


def test_a_stack_missing_from_the_inventory_gives_no_event() -> None:
    outcome = play(start(), (feed(PET, (100, 999999)), False), (updated(pet_entry(experience=262)), True))
    assert outcome == [None, None]


def test_an_unknown_pet_gives_no_event() -> None:
    outcome = play(start(), (feed(123, (100, BONE_STACK)), False), (updated(pet_entry(experience=262)), True))
    assert outcome == [None, None]


def test_without_an_inventory_nothing_can_be_attributed() -> None:
    tracker = PetTracker(SERVER)
    assert play(tracker, (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry()), True)) == [None, None]


def test_an_update_of_another_item_is_ignored() -> None:
    outcome = play(start(), (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(uid=555)), True))
    assert outcome == [None, None]


def test_a_feeding_without_resources_gives_no_event() -> None:
    outcome = play(start(), (feed(PET), False), (updated(pet_entry(experience=262)), True))
    assert outcome == [None, None]


def test_an_update_without_a_feeding_is_ignored_but_refreshes_the_known_state() -> None:
    tracker = start()
    assert play(tracker, (updated(pet_entry(experience=300)), True)) == [None]
    outcome = play(tracker, (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(experience=305)), True))
    assert outcome[1].before.experience == 300


def test_a_new_inventory_replaces_the_old_one() -> None:
    tracker = start()
    tracker.feed(inventory(pet_entry()), True, MOMENT)
    assert play(tracker, (feed(PET, (100, BONE_STACK)), False), (updated(pet_entry(experience=262)), True)) == [None, None]


def test_messages_in_the_wrong_direction_are_ignored() -> None:
    outcome = play(start(), (feed(PET, (100, BONE_STACK)), True), (updated(pet_entry(experience=262)), False))
    assert outcome == [None, None]


def test_unreadable_payloads_are_ignored_without_raising() -> None:
    tracker = start()
    assert play(tracker, (Envelope("irl", b"\xff\xff\xff"), True), (Envelope("irb", b"\x80"), False),
                (Envelope("iqy", b"\xff"), True)) == [None, None, None]


def test_missing_effects_leave_the_state_values_empty() -> None:
    bare = int_field(3, 1) + int_field(4, NOMOON) + int_field(5, PET)
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(stack_entry(BONE, BONE_STACK, 5), bare), True, MOMENT)
    outcome = play(tracker, (feed(PET, (1, BONE_STACK)), False), (updated(pet_entry()), True))
    assert outcome[1].before == PetState(None, None, None, None)
    assert outcome[1].after == PetState(32, 257, 286, 46)
