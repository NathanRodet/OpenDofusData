"""One synchronisation round: send the new local prices, then fetch the other players' prices."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NamedTuple

from opendofusdata.sync_api import SYNC_PAGE_SIZE, SyncFailure, pull_changes, pull_latest_page, push_readings
from opendofusdata.sync_client import UNEXPECTED_MESSAGE
from opendofusdata.sync_rules import valid_cursor
from opendofusdata.sync_store import (
    DATE_FORMAT, clear_state, get_state, insert_remote, mark_sent, pending_readings, set_state,
)

STATE_CURSOR = "cursor"
STATE_LATEST_DONE = "latest_done"
STATE_LATEST_AFTER = "latest_after"
STATE_LATEST_AS_OF = "latest_as_of"
DONE_FLAG = "1"
FIRST_CURSOR = 0
MAX_SYNC_PAGES = 1000  # a server that never ends a feed cannot keep a round busy forever
DONE_MESSAGE = "Synchronisation terminée"
Clock = Callable[[], datetime]


class SyncOptions(NamedTuple):
    """What a round needs: the server, the key, and which directions are switched on."""

    base_url: str
    key: str
    send: bool
    receive: bool


class SyncOutcome(NamedTuple):
    """What a round did: rows sent and received, whether the key was refused, and a message for the player."""

    sent: int
    received: int
    refused: bool
    message: str


@dataclass
class Progress:
    """Counters filled while a round runs, so a failure still reports what was done before it."""

    sent: int = 0
    received: int = 0


def _now(clock: Clock) -> str:
    return clock().strftime(DATE_FORMAT)


def _saved_cursor(connection: sqlite3.Connection, name: str) -> int | None:
    """A saved position as a whole number, or None when absent or garbled."""
    text = get_state(connection, name)
    value = int(text) if text is not None and text.isascii() and text.isdigit() and len(text) < 19 else None
    return value if valid_cursor(value) else None


def _send_all(connection: sqlite3.Connection, options: SyncOptions, clock: Clock, progress: Progress) -> None:
    """Send every pending row in pages; a row is marked sent only after the server accepted its page."""
    for _ in range(MAX_SYNC_PAGES):
        rows = pending_readings(connection, SYNC_PAGE_SIZE, clock())
        if not rows:
            return
        push_readings(options.base_url, options.key, rows)
        mark_sent(connection, [row.row_id for row in rows], _now(clock))
        progress.sent += len(rows)
    raise SyncFailure(UNEXPECTED_MESSAGE)


def _receive_latest(connection: sqlite3.Connection, options: SyncOptions, clock: Clock, progress: Progress) -> None:
    """First run: page through the latest price of every key (resuming after an interruption), then start the
    change cursor at the as_of of the FIRST page, so nothing that arrived during the walk is missed."""
    after = _saved_cursor(connection, STATE_LATEST_AFTER) or FIRST_CURSOR
    starting_point = _saved_cursor(connection, STATE_LATEST_AS_OF)
    for _ in range(MAX_SYNC_PAGES):
        page = pull_latest_page(options.base_url, options.key, after)
        progress.received += insert_remote(connection, page.readings, _now(clock))
        if starting_point is None:
            starting_point = page.as_of
            set_state(connection, STATE_LATEST_AS_OF, str(starting_point))
        if page.done:
            set_state(connection, STATE_CURSOR, str(starting_point))
            set_state(connection, STATE_LATEST_DONE, DONE_FLAG)
            clear_state(connection, STATE_LATEST_AFTER, STATE_LATEST_AS_OF)
            return
        if page.next <= after:
            raise SyncFailure(UNEXPECTED_MESSAGE)
        after = page.next
        set_state(connection, STATE_LATEST_AFTER, str(after))
    raise SyncFailure(UNEXPECTED_MESSAGE)


def _receive_changes(connection: sqlite3.Connection, options: SyncOptions, clock: Clock, progress: Progress) -> None:
    """Fetch the readings that arrived since the saved cursor, page by page, saving the cursor after each page."""
    since = _saved_cursor(connection, STATE_CURSOR) or FIRST_CURSOR
    for _ in range(MAX_SYNC_PAGES):
        readings, following = pull_changes(options.base_url, options.key, since)
        if not readings:
            return
        if following <= since:
            raise SyncFailure(UNEXPECTED_MESSAGE)
        progress.received += insert_remote(connection, readings, _now(clock))
        set_state(connection, STATE_CURSOR, str(following))
        since = following
    raise SyncFailure(UNEXPECTED_MESSAGE)


def _receive(connection: sqlite3.Connection, options: SyncOptions, clock: Clock, progress: Progress) -> None:
    """Snapshot first when never done (or when the saved cursor is garbled), then the change feed."""
    if get_state(connection, STATE_LATEST_DONE) == DONE_FLAG and _saved_cursor(connection, STATE_CURSOR) is None:
        clear_state(connection, STATE_LATEST_DONE, STATE_CURSOR)
    if get_state(connection, STATE_LATEST_DONE) != DONE_FLAG:
        _receive_latest(connection, options, clock, progress)
    _receive_changes(connection, options, clock, progress)


def sync_once(connection: sqlite3.Connection, options: SyncOptions,
              clock: Clock = lambda: datetime.now(timezone.utc)) -> SyncOutcome:
    """Run one round. A refused key ends it; any other failure of the send leaves the receive running."""
    progress, problem = Progress(), None
    try:
        if options.send:
            _send_all(connection, options, clock, progress)
    except SyncFailure as failure:
        if failure.refused:
            return SyncOutcome(progress.sent, progress.received, True, str(failure))
        problem = failure
    try:
        if options.receive:
            _receive(connection, options, clock, progress)
    except SyncFailure as failure:
        return SyncOutcome(progress.sent, progress.received, failure.refused, str(failure))
    return SyncOutcome(progress.sent, progress.received, False, str(problem) if problem else DONE_MESSAGE)
