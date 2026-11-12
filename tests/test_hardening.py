"""Defensive behaviour found by the security review: no silent coercions, bounded state, safe logs."""

import logging

from opendofusdata import crafting_window, pets
from opendofusdata.categories import CATEGORY_HDV, CategorySettings, FilteringWriter, category_of
from opendofusdata.crafting_window import CraftingWindow
from opendofusdata.framing import Envelope
from opendofusdata.log_feed import entry_from_record
from opendofusdata.pets import PetTracker
from opendofusdata.records import BrokenItem, LotPrice, PetFeeding, PetState
from tests.envelopes import bytes_field, int_field
from tests.test_pets import (
    BONE, BONE_STACK, MOMENT, SERVER, feed, inventory, pet_entry, stack_entry, updated,
)
from tests.test_recycling import added, updated as window_updated

EMPTY_STATE = PetState(None, None, None, None)


class ListSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def submit(self, record: object) -> None:
        self.records.append(record)


def test_a_feed_request_without_a_pet_never_matches_the_object_with_instance_zero() -> None:
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(stack_entry(BONE, BONE_STACK, 5), pet_entry(uid=0)), True, MOMENT)
    no_pet = Envelope("irb", bytes_field(3, int_field(1, 100) + int_field(3, BONE_STACK)))
    assert tracker.feed(no_pet, False, MOMENT) is None
    assert tracker.feed(updated(pet_entry(uid=0, experience=300)), True, MOMENT) is None


def test_a_resource_without_a_stack_never_matches_the_object_with_instance_zero() -> None:
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(stack_entry(BONE, 0, 5), pet_entry()), True, MOMENT)
    no_stack = Envelope("irb", int_field(2, 4409814) + bytes_field(3, int_field(1, 100)))
    assert tracker.feed(no_stack, False, MOMENT) is None
    assert tracker.feed(updated(pet_entry(experience=300)), True, MOMENT) is None


def test_the_known_objects_of_the_pet_tracker_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr(pets, "MAX_KNOWN_OBJECTS", 3)
    tracker = PetTracker(SERVER)
    tracker.feed(inventory(*(stack_entry(BONE, 1000 + index, 1) for index in range(10))), True, MOMENT)
    assert len(tracker._objects) <= 3
    for index in range(10):
        tracker.feed(updated(pet_entry(uid=5000 + index)), True, MOMENT)
    assert len(tracker._objects) <= 3


def test_the_window_entries_are_bounded_but_known_stacks_still_update(monkeypatch) -> None:
    monkeypatch.setattr(crafting_window, "MAX_WINDOW_ENTRIES", 2)
    window = CraftingWindow()
    for stack in (11, 12, 13):
        window.handle(added(1, BONE, stack), True)
    assert sorted(window.entries) == [11, 12]
    window.handle(window_updated(9, BONE, 11), True)
    assert window.entries[11] == (BONE, 9)


def test_a_pet_feeding_without_resources_can_be_logged() -> None:
    feeding = PetFeeding(SERVER, 6716, (), EMPTY_STATE, EMPTY_STATE, "t")
    assert entry_from_record(feeding, MOMENT_DATETIME).item_id == 0


def test_a_broken_object_without_rune_can_be_logged() -> None:
    entry = entry_from_record(BrokenItem(SERVER, 942, 1, 0.5, (), "t"), MOMENT_DATETIME)
    assert (entry.item_id, entry.detail, entry.value) == (942, "50 %", "0 rune")


def test_an_unknown_record_type_has_no_category_and_is_dropped_and_logged(caplog) -> None:
    class Unknown:
        pass

    sink = ListSink()
    assert category_of(Unknown()) is None
    with caplog.at_level(logging.WARNING):
        FilteringWriter(sink, CategorySettings([CATEGORY_HDV])).submit(Unknown())
    assert sink.records == []
    assert "Unknown" in caplog.text


def test_known_record_types_keep_their_category() -> None:
    assert category_of(LotPrice(1, "x", 1, 1, "t")) == CATEGORY_HDV


from datetime import datetime, timezone  # noqa: E402

MOMENT_DATETIME = datetime(2026, 11, 11, tzinfo=timezone.utc)
