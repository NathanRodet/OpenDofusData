"""Breaking through the whole chain: store, handler, category filter, counters and logs."""

import threading
from datetime import datetime, timezone

from opendofusdata.breaking_store import breaking_events
from opendofusdata.capture_session import CaptureSession
from opendofusdata.categories import (
    CATEGORY_BREAKING, CATEGORY_HDV, CategorySettings, FilteringWriter, category_of,
)
from opendofusdata.log_feed import LogFeed, entry_from_record, format_log_row
from opendofusdata.records import BreakingEvent, BrokenItem
from opendofusdata.run_pipeline import make_envelope_handler
from opendofusdata.storage import PriceStore, StoreWriter
from tests.envelopes import FLOW_KEY
from tests.test_breaking import (
    AGE, EBONY_STACK, FIFTY_THREE, GA_PA, INE, ORCHID_STACK, VOLKORNE_EBONY, VOLKORNE_ORCHID,
    break_request, broken, outcome,
)
from tests.test_recycling import added

MOMENT = datetime(2026, 11, 11, 19, 27, 56, tzinfo=timezone.utc)
CLIENT_KEY = (FLOW_KEY[2], FLOW_KEY[3], FLOW_KEY[0], FLOW_KEY[1])
EVENT = BreakingEvent("Brial", (
    BrokenItem(VOLKORNE_ORCHID, 1, 0.5, ((GA_PA, 1), (INE, 38))),
    BrokenItem(VOLKORNE_EBONY, 1, 0.5, ((AGE, 38),))), "2026-11-11T19:27:56Z")


class ListSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def submit(self, record: object) -> None:
        self.records.append(record)


def play(handler) -> None:
    handler(added(1, VOLKORNE_ORCHID, ORCHID_STACK), FLOW_KEY)
    handler(added(1, VOLKORNE_EBONY, EBONY_STACK), FLOW_KEY)
    handler(break_request(2), CLIENT_KEY)
    handler(broken(outcome(ORCHID_STACK, ((1, GA_PA), (38, INE))), outcome(EBONY_STACK, ((38, AGE),))), FLOW_KEY)


def test_the_table_round_trips_coefficients_and_runes(tmp_path) -> None:
    other = BreakingEvent("Brial", (BrokenItem(942, 1, FIFTY_THREE, ()),), "2026-11-11T19:26:40Z")
    store = PriceStore(str(tmp_path / "b.db"))
    try:
        store.save_record(EVENT)
        store.save_record(other)
        assert breaking_events(store.connection) == [other, EVENT]
    finally:
        store.close()


def test_the_writer_thread_saves_breaking_events(tmp_path) -> None:
    writer = StoreWriter(str(tmp_path / "b.db"))
    writer.submit(EVENT)
    writer.stop()
    store = PriceStore(str(tmp_path / "b.db"))
    try:
        assert breaking_events(store.connection) == [EVENT]
    finally:
        store.close()


def test_the_handler_emits_one_event_from_real_messages_and_no_recycling() -> None:
    sink = ListSink()
    play(make_envelope_handler(sink, "Brial", lambda: MOMENT))
    assert sink.records == [EVENT]


def test_category_and_filter() -> None:
    assert category_of(EVENT) == CATEGORY_BREAKING
    off, on = ListSink(), ListSink()
    FilteringWriter(off, CategorySettings([CATEGORY_HDV])).submit(EVENT)
    FilteringWriter(on, CategorySettings([CATEGORY_BREAKING])).submit(EVENT)
    assert (off.records, on.records) == ([], [EVENT])


def run_session(tmp_path, categories: CategorySettings, feed: LogFeed | None = None) -> CaptureSession:
    done = threading.Event()

    def capture(pipeline, interface, stop) -> None:
        play(lambda envelope, key: pipeline.on_envelope(envelope, key))
        done.set()
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "s.db"), "Brial", None, capture, lambda: MOMENT,
                             categories=categories, feed=feed)
    session.start()
    assert done.wait(5.0)
    for _ in range(300):
        if session.snapshot().breaking_count:
            break
        threading.Event().wait(0.01)
    session.stop()
    return session


def test_an_enabled_breaking_is_counted_stored_and_logged(tmp_path) -> None:
    feed = LogFeed()
    feed.set_visible(True)
    session = run_session(tmp_path, CategorySettings([CATEGORY_BREAKING]), feed)
    assert session.snapshot().breaking_count == 1
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert breaking_events(store.connection) == [EVENT]
    finally:
        store.close()
    assert feed.entries()[0].category == "Brisage"


def test_a_disabled_breaking_is_neither_counted_nor_stored(tmp_path) -> None:
    session = run_session(tmp_path, CategorySettings([CATEGORY_HDV]))
    assert session.snapshot().breaking_count == 0
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert breaking_events(store.connection) == []
    finally:
        store.close()


NAMES = {VOLKORNE_ORCHID: "Volkorne Orchidée", VOLKORNE_EBONY: "Volkorne Ébène", 942: "Lisseur"}


def test_the_log_row_names_the_objects_and_sums_the_runes() -> None:
    row = format_log_row(entry_from_record(EVENT, MOMENT), NAMES.__getitem__)
    assert row[1:] == ("Brisage", "Volkorne Orchidée ×1, Volkorne Ébène ×1", "50 %", "77 runes")


def test_mixed_coefficients_are_shown_as_a_range_and_zero_runes_are_singular() -> None:
    mixed = BreakingEvent("Brial", (BrokenItem(942, 1, 0.5, ()), BrokenItem(33166, 1, FIFTY_THREE, ())), "t")
    entry = entry_from_record(mixed, MOMENT)
    assert (entry.detail, entry.value) == ("50-53 %", "0 rune")
