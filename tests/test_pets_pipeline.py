"""Pets through the whole chain: store, handler, category filter, counters and logs."""

import threading
from datetime import datetime, timezone

from opendofusdata.categories import CATEGORY_HDV, CATEGORY_PETS, CategorySettings, FilteringWriter, category_of
from opendofusdata.capture_session import CaptureSession
from opendofusdata.log_feed import LogFeed, entry_from_record, format_log_row
from opendofusdata.pets_store import pet_feedings
from opendofusdata.records import PetFeeding, PetState
from opendofusdata.run_pipeline import make_envelope_handler
from opendofusdata.storage import PriceStore, StoreWriter
from tests.envelopes import FLOW_KEY
from tests.test_pets import BONE, BONE_STACK, EYE, EYE_STACK, NOMOON, PET, feed, inventory, pet_entry, stack_entry, updated

MOMENT = datetime(2026, 11, 11, 19, 25, 6, tzinfo=timezone.utc)
CLIENT_KEY = (FLOW_KEY[2], FLOW_KEY[3], FLOW_KEY[0], FLOW_KEY[1])
FEEDING = PetFeeding("Brial", NOMOON, ((BONE, 100),), PetState(32, 257, 286, 46), PetState(32, 262, 286, 46),
                     "2026-11-11T19:25:06Z")
LEVEL_UP = PetFeeding("Brial", NOMOON, ((BONE, 125), (EYE, 2)), PetState(31, 240, 286, 45),
                      PetState(32, 5, 300, 46), "2026-11-11T19:17:06Z")


class ListSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def submit(self, record: object) -> None:
        self.records.append(record)


def play(handler) -> None:
    handler(inventory(stack_entry(BONE, BONE_STACK, 4787), stack_entry(EYE, EYE_STACK, 35), pet_entry()), FLOW_KEY)
    handler(feed(PET, (100, BONE_STACK)), CLIENT_KEY)
    handler(updated(pet_entry(experience=262)), FLOW_KEY)


def test_the_table_round_trips_both_states_and_the_resources(tmp_path) -> None:
    store = PriceStore(str(tmp_path / "p.db"))
    try:
        store.save_record(LEVEL_UP)
        store.save_record(FEEDING)
        assert pet_feedings(store.connection) == [LEVEL_UP, FEEDING]
    finally:
        store.close()


def test_missing_state_values_survive_the_round_trip(tmp_path) -> None:
    sparse = PetFeeding("Brial", NOMOON, ((BONE, 1),), PetState(None, None, None, None), PetState(32, 1, 2, None), "t")
    store = PriceStore(str(tmp_path / "p.db"))
    try:
        store.save_record(sparse)
        assert pet_feedings(store.connection) == [sparse]
    finally:
        store.close()


def test_the_writer_thread_saves_pet_feedings(tmp_path) -> None:
    writer = StoreWriter(str(tmp_path / "p.db"))
    writer.submit(FEEDING)
    writer.stop()
    store = PriceStore(str(tmp_path / "p.db"))
    try:
        assert pet_feedings(store.connection) == [FEEDING]
    finally:
        store.close()


def test_the_handler_emits_the_event_from_real_messages() -> None:
    sink = ListSink()
    play(make_envelope_handler(sink, "Brial", lambda: MOMENT))
    assert sink.records == [FEEDING]


def test_category_and_filter() -> None:
    assert category_of(FEEDING) == CATEGORY_PETS
    off, on = ListSink(), ListSink()
    FilteringWriter(off, CategorySettings([CATEGORY_HDV])).submit(FEEDING)
    FilteringWriter(on, CategorySettings([CATEGORY_PETS])).submit(FEEDING)
    assert (off.records, on.records) == ([], [FEEDING])


def test_an_enabled_pet_upgrade_is_counted_stored_and_logged(tmp_path) -> None:
    feed_log = LogFeed()
    feed_log.set_visible(True)

    def capture(pipeline, interface, stop) -> None:
        play(lambda envelope, key: pipeline.on_envelope(envelope, key))
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "s.db"), "Brial", None, capture, lambda: MOMENT,
                             categories=CategorySettings([CATEGORY_PETS]), feed=feed_log)
    session.start()
    for _ in range(500):
        if session.snapshot().pet_count:
            break
        threading.Event().wait(0.01)
    session.stop()
    assert session.snapshot().pet_count == 1
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert pet_feedings(store.connection) == [FEEDING]
    finally:
        store.close()
    assert feed_log.entries()[0].category == "Familier"


def test_a_disabled_pet_category_is_neither_counted_nor_stored(tmp_path) -> None:
    ran = threading.Event()

    def capture(pipeline, interface, stop) -> None:
        play(lambda envelope, key: pipeline.on_envelope(envelope, key))
        ran.set()
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "s.db"), "Brial", None, capture, lambda: MOMENT,
                             categories=CategorySettings([CATEGORY_HDV]))
    session.start()
    assert ran.wait(5.0)
    session.stop()
    assert session.snapshot().pet_count == 0
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert pet_feedings(store.connection) == []
    finally:
        store.close()


def test_the_log_row_shows_the_resources_the_level_and_the_experience_gain() -> None:
    names = {BONE: "Os de Chafer", EYE: "Œil de Truchtine"}.__getitem__
    row = format_log_row(entry_from_record(FEEDING, MOMENT), names)
    assert row[1:] == ("Familier", "Os de Chafer ×100", "niv 32", "+5 XP")


def test_a_level_up_is_shown_as_levels_gained() -> None:
    entry = entry_from_record(LEVEL_UP, MOMENT)
    assert (entry.detail, entry.value) == ("niv 32", "+1 niv")


def test_an_unknown_state_shows_a_dash() -> None:
    unknown = PetFeeding("Brial", NOMOON, ((BONE, 1),), PetState(None, None, None, None), PetState(None, None, None, None), "t")
    entry = entry_from_record(unknown, MOMENT)
    assert (entry.detail, entry.value) == ("niv ?", "+? XP")
