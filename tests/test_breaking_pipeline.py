"""Breaking through the whole chain: one record per object in the store, the logs and the counters."""

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone

from opendofusdata.breaking_store import broken_items
from opendofusdata.capture_session import CaptureSession
from opendofusdata.categories import (
    CATEGORY_BREAKING, CATEGORY_HDV, CategorySettings, FilteringWriter, category_of,
)
from opendofusdata.log_feed import LogFeed, entry_from_record, format_log_line, format_log_row
from opendofusdata.records import BrokenItem
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
STAMP = "2026-11-11T19:27:56Z"
ORCHID = BrokenItem("Brial", VOLKORNE_ORCHID, 1, 0.5, ((GA_PA, 1), (INE, 38)), STAMP)
EBONY = BrokenItem("Brial", VOLKORNE_EBONY, 1, 0.5, ((AGE, 38),), STAMP)


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


def test_each_object_is_one_row_with_its_own_coefficient_and_runes(tmp_path) -> None:
    lisseur = BrokenItem("Brial", 942, 1, FIFTY_THREE, (), "2026-11-11T19:26:40Z")
    store = PriceStore(str(tmp_path / "b.db"))
    try:
        for record in (ORCHID, EBONY, lisseur):
            store.save_record(record)
        assert broken_items(store.connection) == [lisseur, ORCHID, EBONY]
        rows = store.connection.execute("SELECT item_id, quantity, coefficient FROM broken_items ORDER BY id").fetchall()
        assert rows == [(VOLKORNE_ORCHID, 1, 0.5), (VOLKORNE_EBONY, 1, 0.5), (942, 1, FIFTY_THREE)]
    finally:
        store.close()


def test_old_batch_rows_are_split_into_one_row_per_object_and_the_old_table_is_dropped(tmp_path) -> None:
    with closing(sqlite3.connect(tmp_path / "old.db")) as connection:
        connection.execute("CREATE TABLE breaking_events (id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT NOT NULL, "
                           "captured_at TEXT NOT NULL, items_json TEXT NOT NULL)")
        items = [[VOLKORNE_ORCHID, 1, 0.5, [[GA_PA, 1], [INE, 38]]], [VOLKORNE_EBONY, 2, 0.5, [[AGE, 38]]]]
        connection.execute("INSERT INTO breaking_events (server, captured_at, items_json) VALUES (?, ?, ?)",
                           ("Brial", STAMP, json.dumps(items)))
        connection.commit()
    store = PriceStore(str(tmp_path / "old.db"))
    try:
        assert broken_items(store.connection) == [ORCHID, BrokenItem("Brial", VOLKORNE_EBONY, 2, 0.5, ((AGE, 38),), STAMP)]
        tables = {row[0] for row in store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "breaking_events" not in tables
    finally:
        store.close()
    reopened = PriceStore(str(tmp_path / "old.db"))
    try:
        assert len(broken_items(reopened.connection)) == 2  # the migration does not run twice
    finally:
        reopened.close()


def test_the_writer_thread_saves_broken_items(tmp_path) -> None:
    writer = StoreWriter(str(tmp_path / "b.db"))
    writer.submit(ORCHID)
    writer.stop()
    store = PriceStore(str(tmp_path / "b.db"))
    try:
        assert broken_items(store.connection) == [ORCHID]
    finally:
        store.close()


def test_the_handler_emits_one_record_per_object_and_no_recycling() -> None:
    sink = ListSink()
    play(make_envelope_handler(sink, "Brial", lambda: MOMENT))
    assert sink.records == [ORCHID, EBONY]


def test_category_and_filter() -> None:
    assert category_of(ORCHID) == CATEGORY_BREAKING
    off, on = ListSink(), ListSink()
    FilteringWriter(off, CategorySettings([CATEGORY_HDV])).submit(ORCHID)
    FilteringWriter(on, CategorySettings([CATEGORY_BREAKING])).submit(ORCHID)
    assert (off.records, on.records) == ([], [ORCHID])


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
        if session.snapshot().breaking_count >= 2:
            break
        threading.Event().wait(0.01)
    session.stop()
    return session


def test_an_enabled_breaking_counts_stores_and_logs_one_line_per_object(tmp_path) -> None:
    feed = LogFeed()
    feed.set_visible(True)
    session = run_session(tmp_path, CategorySettings([CATEGORY_BREAKING]), feed)
    assert session.snapshot().breaking_count == 2
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert broken_items(store.connection) == [ORCHID, EBONY]
    finally:
        store.close()
    assert [entry.category for entry in feed.entries()] == ["Brisage", "Brisage"]


def test_a_disabled_breaking_is_neither_counted_nor_stored(tmp_path) -> None:
    session = run_session(tmp_path, CategorySettings([CATEGORY_HDV]))
    assert session.snapshot().breaking_count == 0
    store = PriceStore(str(tmp_path / "s.db"))
    try:
        assert broken_items(store.connection) == []
    finally:
        store.close()


NAMES = {VOLKORNE_ORCHID: "Volkorne Orchidée", VOLKORNE_EBONY: "Volkorne Ébène", 942: "Lisseur"}


def test_each_log_line_shows_the_object_its_coefficient_and_its_runes() -> None:
    assert format_log_row(entry_from_record(ORCHID, MOMENT), NAMES.__getitem__)[1:] == (
        "Brisage", "Volkorne Orchidée ×1", "50 %", "39 runes")
    assert format_log_row(entry_from_record(EBONY, MOMENT), NAMES.__getitem__)[1:] == (
        "Brisage", "Volkorne Ébène ×1", "50 %", "38 runes")


def test_a_stack_shows_its_quantity_and_an_object_without_rune_shows_zero() -> None:
    stack = BrokenItem("Brial", 942, 2, FIFTY_THREE, (), "t")
    row = format_log_row(entry_from_record(stack, MOMENT), NAMES.__getitem__)
    assert row[1:] == ("Brisage", "Lisseur ×2", "53 %", "0 rune")
    assert "Lisseur ×2" in format_log_line(row)
