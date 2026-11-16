"""The local side of the shared events: rows still to send, sent marks, events received or restored."""

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from opendofusdata.event_kinds import EventKind
from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE
from opendofusdata.sync_store import DATE_FORMAT, SEND_MAX_AGE_DAYS, SKIPPED


class PendingEvent(NamedTuple):
    """One local row to send: its row number and the event that goes on the wire."""

    row_id: int
    event: dict[str, object]


def _unsent_sql(kind: EventKind) -> str:
    return (f"SELECT id, {', '.join(kind.columns)} FROM {kind.table} "
            f"WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL ORDER BY captured_at, id")


def _skip(connection: sqlite3.Connection, kind: EventKind, row_ids: Sequence[int]) -> None:
    with connection:
        connection.executemany(f"UPDATE {kind.table} SET synced_at = '{SKIPPED}' WHERE id = ?",
                               [(row_id,) for row_id in row_ids])


def pending_events(connection: sqlite3.Connection, kind: EventKind, limit: int,
                   now: datetime | None = None) -> list[PendingEvent]:
    """The oldest local rows worth sending (at most `limit`); expired and invalid rows are marked skipped."""
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=SEND_MAX_AGE_DAYS)).strftime(DATE_FORMAT)
    with connection:
        connection.execute(f"UPDATE {kind.table} SET synced_at = '{SKIPPED}' WHERE origin = '{ORIGIN_LOCAL}' "
                           "AND synced_at IS NULL AND captured_at < ?", (cutoff,))
    wanted: list[PendingEvent] = []
    invalid: list[int] = []
    for row in connection.execute(_unsent_sql(kind)).fetchall():
        if len(wanted) == limit:
            break
        event = kind.to_event(tuple(row[1:]))
        if kind.valid(event):
            wanted.append(PendingEvent(row[0], event))
        else:
            invalid.append(row[0])
    _skip(connection, kind, invalid)
    return wanted


def mark_events_sent(connection: sqlite3.Connection, kind: EventKind, row_ids: Sequence[int], moment: str) -> None:
    """Remember that the server has these rows."""
    with connection:
        connection.executemany(f"UPDATE {kind.table} SET synced_at = ? WHERE id = ?",
                               [(moment, row_id) for row_id in row_ids])


def insert_other_events(connection: sqlite3.Connection, kind: EventKind, events: Sequence[Mapping[str, object]],
                        moment: str) -> int:
    """Store events received from other players (remote, already synced); returns the new rows."""
    columns = ", ".join(kind.columns)
    marks = ", ".join("?" * len(kind.columns))
    sql = (f"INSERT OR IGNORE INTO {kind.table} ({columns}, origin, synced_at, source_key_id) "
           f"VALUES ({marks}, '{ORIGIN_REMOTE}', ?, ?)")
    before = connection.total_changes
    with connection:
        connection.executemany(sql, [(*kind.to_values(event), moment, event["key_id"]) for event in events])
    return connection.total_changes - before


def insert_own_events(connection: sqlite3.Connection, kind: EventKind, events: Sequence[Mapping[str, object]],
                      moment: str) -> int:
    """Store events this player sent earlier (local, already synced), skipping the ones already here."""
    columns = ", ".join(kind.columns)
    marks = ", ".join("?" * len(kind.columns))
    same = " AND ".join(f"{column} = ?" for column in kind.columns)
    sql = (f"INSERT INTO {kind.table} ({columns}, origin, synced_at) SELECT {marks}, '{ORIGIN_LOCAL}', ? "
           f"WHERE NOT EXISTS (SELECT 1 FROM {kind.table} WHERE origin = '{ORIGIN_LOCAL}' AND {same})")
    before = connection.total_changes
    with connection:
        connection.executemany(sql, [(*kind.to_values(event), moment, *kind.to_values(event)) for event in events])
    return connection.total_changes - before
