"""The counters shown under the key: readings sent out of those to send, readings received."""

import sqlite3

from opendofusdata.storage import PriceStore
from opendofusdata.sync_counts import SyncCounts, count_sync, counts_text, read_counts_text
from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE
from opendofusdata.sync_store import SKIPPED

INSERT = ("INSERT INTO lot_prices (item_id, server, lot_size, price, captured_at, origin, synced_at) "
          "VALUES (?, 'Brial', 1, 10, ?, ?, ?)")


def make_connection(tmp_path) -> sqlite3.Connection:
    return PriceStore(str(tmp_path / "prices.db")).connection


def test_an_empty_database_counts_zero(tmp_path) -> None:
    assert count_sync(make_connection(tmp_path)) == SyncCounts(sent=0, to_send=0, received=0)


def test_sent_rows_are_counted_out_of_the_local_rows_worth_sending(tmp_path) -> None:
    connection = make_connection(tmp_path)
    connection.executemany(INSERT, [
        (1, "2026-11-16T10:00:00Z", ORIGIN_LOCAL, "2026-11-16T10:05:00Z"),
        (2, "2026-11-16T10:00:00Z", ORIGIN_LOCAL, None),
        (3, "2026-11-16T10:00:00Z", ORIGIN_LOCAL, SKIPPED),
        (4, "2026-11-16T10:00:00Z", ORIGIN_REMOTE, "2026-11-16T10:05:00Z"),
    ])
    assert count_sync(connection) == SyncCounts(sent=1, to_send=2, received=1)


def test_the_text_shows_both_counters() -> None:
    assert counts_text(SyncCounts(sent=3, to_send=5, received=12)) == "Envoyés : 3/5. Reçus des autres joueurs : 12."


def test_the_line_is_read_from_a_database_file(tmp_path) -> None:
    connection = make_connection(tmp_path)
    connection.execute(INSERT, (1, "2026-11-16T10:00:00Z", ORIGIN_REMOTE, "2026-11-16T10:05:00Z"))
    connection.commit()
    assert read_counts_text(str(tmp_path / "prices.db")) == "Envoyés : 0/0. Reçus des autres joueurs : 1."


def test_a_missing_database_gives_no_line(tmp_path) -> None:
    assert read_counts_text(str(tmp_path / "absent.db")) == ""
