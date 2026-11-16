"""One round for the shared events (breakings, pet upgrades): send ours, fetch the others', restore ours once."""

import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from opendofusdata.event_api import pull_event_changes, pull_event_own, push_events
from opendofusdata.event_kinds import EVENT_KINDS, EventKind
from opendofusdata.event_sync_store import insert_other_events, insert_own_events, mark_events_sent, pending_events
from opendofusdata.sync_api import SYNC_PAGE_SIZE, SyncFailure
from opendofusdata.sync_client import UNEXPECTED_MESSAGE
from opendofusdata.sync_rules import valid_cursor
from opendofusdata.sync_store import DATE_FORMAT, clear_state, get_state, set_state

MAX_EVENT_PAGES = 1000  # a server that never ends a feed cannot keep a round busy forever
DONE_FLAG = "1"
FIRST_CURSOR = 0
Clock = Callable[[], datetime]


class Counters(Protocol):
    """What a round counts: rows sent and rows received."""

    sent: int
    received: int


class Options(Protocol):
    """What a round needs from the synchronisation options."""

    base_url: str
    key: str
    send: bool
    receive: bool


def _state_name(kind: EventKind, what: str) -> str:
    return f"events_{kind.name}_{what}"


def _saved(connection: sqlite3.Connection, name: str) -> int:
    text = get_state(connection, name)
    value = int(text) if text is not None and text.isascii() and text.isdigit() and len(text) < 19 else None
    return value if valid_cursor(value) else FIRST_CURSOR


def _send(connection: sqlite3.Connection, kind: EventKind, options: Options, clock: Clock, counters: Counters) -> None:
    for _ in range(MAX_EVENT_PAGES):
        rows = pending_events(connection, kind, SYNC_PAGE_SIZE, clock())
        if not rows:
            return
        push_events(options.base_url, options.key, kind, [row.event for row in rows])
        mark_events_sent(connection, kind, [row.row_id for row in rows], clock().strftime(DATE_FORMAT))
        counters.sent += len(rows)
    raise SyncFailure(UNEXPECTED_MESSAGE)


def _receive(connection: sqlite3.Connection, kind: EventKind, options: Options, clock: Clock,
             counters: Counters) -> None:
    name = _state_name(kind, "cursor")
    since = _saved(connection, name)
    for _ in range(MAX_EVENT_PAGES):
        events, following = pull_event_changes(options.base_url, options.key, kind, since)
        if not events:
            return
        if following <= since:
            raise SyncFailure(UNEXPECTED_MESSAGE)
        counters.received += insert_other_events(connection, kind, events, clock().strftime(DATE_FORMAT))
        set_state(connection, name, str(following))
        since = following
    raise SyncFailure(UNEXPECTED_MESSAGE)


def _restore_own(connection: sqlite3.Connection, kind: EventKind, options: Options, clock: Clock,
                 counters: Counters) -> None:
    done, name = _state_name(kind, "own_done"), _state_name(kind, "own_after")
    if get_state(connection, done) == DONE_FLAG:
        return
    after = _saved(connection, name)
    for _ in range(MAX_EVENT_PAGES):
        events, following = pull_event_own(options.base_url, options.key, kind, after)
        if not events:
            set_state(connection, done, DONE_FLAG)
            clear_state(connection, name)
            return
        if following <= after:
            raise SyncFailure(UNEXPECTED_MESSAGE)
        counters.received += insert_own_events(connection, kind, events, clock().strftime(DATE_FORMAT))
        after = following
        set_state(connection, name, str(after))
    raise SyncFailure(UNEXPECTED_MESSAGE)


def sync_events(connection: sqlite3.Connection, options: Options, clock: Clock, counters: Counters) -> None:
    """Run every kind in turn: send, then receive and restore (a failure stops the round and is raised)."""
    for kind in EVENT_KINDS:
        if options.send:
            _send(connection, kind, options, clock, counters)
        if options.receive:
            _receive(connection, kind, options, clock, counters)
            _restore_own(connection, kind, options, clock, counters)
