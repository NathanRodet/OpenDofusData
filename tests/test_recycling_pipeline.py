"""Recycling through the whole chain: handler, category filter, session counters and logs."""

import threading
from datetime import datetime, timezone

from opendofusdata.capture_session import CaptureSession
from opendofusdata.categories import (
    CATEGORY_HDV, CATEGORY_RECYCLING, CategorySettings, FilteringWriter, category_of,
)
from opendofusdata.log_feed import LogFeed, entry_from_record, format_log_row
from opendofusdata.records import LotPrice, RecyclingEvent
from opendofusdata.recycling_store import recycling_events
from opendofusdata.run_pipeline import make_envelope_handler
from opendofusdata.storage import PriceStore
from tests.envelopes import FLOW_KEY, lot_envelope
from tests.test_recycling import OS_OF_CHAFER, OS_STACK, added, request, result

MOMENT = datetime(2026, 11, 11, 19, 18, 30, tzinfo=timezone.utc)
CLIENT_KEY = (FLOW_KEY[2], FLOW_KEY[3], FLOW_KEY[0], FLOW_KEY[1])  # the client side talks to the server port


class ListSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def submit(self, record: object) -> None:
        self.records.append(record)


def recycle(handler, nuggets: int = 3, quantity: int = 1000) -> None:
    handler(added(quantity, OS_OF_CHAFER, OS_STACK), FLOW_KEY)
    handler(request(), CLIENT_KEY)
    handler(result(nuggets), FLOW_KEY)


def test_the_handler_submits_one_event_per_recycling_with_the_capture_time() -> None:
    sink = ListSink()
    recycle(make_envelope_handler(sink, "Brial", lambda: MOMENT))
    assert sink.records == [RecyclingEvent("Brial", ((OS_OF_CHAFER, 1000),), 3, "2026-11-11T19:18:30Z")]


def test_the_handler_still_decodes_hdv_prices_alongside() -> None:
    sink = ListSink()
    handler = make_envelope_handler(sink, "Brial", lambda: MOMENT)
    handler(lot_envelope(), FLOW_KEY)
    recycle(handler)
    assert [type(record) for record in sink.records].count(LotPrice) == 4
    assert [type(record) for record in sink.records].count(RecyclingEvent) == 1


def test_category_of_maps_each_record_type() -> None:
    assert category_of(LotPrice(1, "x", 1, 1, "t")) == CATEGORY_HDV
    assert category_of(RecyclingEvent("x", (), 0, "t")) == CATEGORY_RECYCLING


def test_the_filter_drops_recycling_unless_its_category_is_enabled() -> None:
    event = RecyclingEvent("Brial", ((310, 1),), 0, "t")
    off, on = ListSink(), ListSink()
    FilteringWriter(off, CategorySettings([CATEGORY_HDV])).submit(event)
    FilteringWriter(on, CategorySettings([CATEGORY_RECYCLING])).submit(event)
    assert (off.records, on.records) == ([], [event])


def test_the_filter_keeps_hdv_independent_of_recycling() -> None:
    lot, sink = LotPrice(1, "x", 1, 1, "t"), ListSink()
    FilteringWriter(sink, CategorySettings([CATEGORY_RECYCLING])).submit(lot)
    assert sink.records == []


def test_an_enabled_recycling_is_counted_stored_and_logged(tmp_path) -> None:
    feed = LogFeed()
    feed.set_visible(True)

    def capture(pipeline, interface, stop) -> None:
        recycle(lambda envelope, key: pipeline.on_envelope(envelope, key))
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "s.db"), "Brial", None, capture, lambda: MOMENT,
                             categories=CategorySettings([CATEGORY_RECYCLING]), feed=feed)
    session.start()
    for _ in range(500):
        if session.snapshot().recycling_count:
            break
        threading.Event().wait(0.01)
    session.stop()
    assert session.snapshot().recycling_count == 1
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert recycling_events(store.connection)[0].nuggets == 3
    finally:
        store.close()
    entry = feed.entries()[0]
    assert (entry.category, entry.detail, entry.value) == ("Recyclage", "1 objet", "3 Pépites")


def test_a_disabled_recycling_is_neither_counted_nor_stored(tmp_path) -> None:
    ran = threading.Event()

    def capture(pipeline, interface, stop) -> None:
        recycle(lambda envelope, key: pipeline.on_envelope(envelope, key))
        ran.set()
        stop.wait(5.0)

    session = CaptureSession(str(tmp_path / "s.db"), "Brial", None, capture, lambda: MOMENT,
                             categories=CategorySettings([CATEGORY_HDV]))
    session.start()
    assert ran.wait(5.0)
    session.stop()
    assert session.snapshot().recycling_count == 0
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert recycling_events(store.connection) == []
    finally:
        store.close()


def test_the_log_row_names_every_item_and_pluralises_the_nuggets() -> None:
    event = RecyclingEvent("Brial", ((310, 100), (15073, 10)), 0, "t")
    entry = entry_from_record(event, MOMENT)
    row = format_log_row(entry, lambda item_id: {310: "Os de Chafer", 15073: "Œil de Truchtine"}[item_id])
    assert row[1:] == ("Recyclage", "Os de Chafer ×100, Œil de Truchtine ×10", "2 objets", "0 Pépite")
    assert entry_from_record(RecyclingEvent("x", ((1, 1),), 2, "t"), MOMENT).value == "2 Pépites"
