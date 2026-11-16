"""The local side of the synchronisation: readings still to send, marks, readings received, sync state."""

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from opendofusdata.sync_rules import valid_price_data
from opendofusdata.sync_schema import ORIGIN_LOCAL, ORIGIN_REMOTE

MIN_RESEND_SECONDS = 3600
SEND_MAX_AGE_DAYS = 7  # the server keeps readings seven days: older ones are never worth sending
SKIPPED = "skipped"  # synced_at of a row left out on purpose (never a reference for the resend filter)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UNSENT_SQL = f"""
    SELECT id, item_id, server, lot_size, price, captured_at FROM lot_prices
    WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL ORDER BY captured_at, id"""
LAST_SENT_SQL = f"""
    SELECT price, captured_at FROM lot_prices
    WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NOT NULL AND synced_at != '{SKIPPED}'
      AND item_id = ? AND server = ? AND lot_size = ? AND captured_at <= ?
    ORDER BY captured_at DESC, id DESC LIMIT 1"""
EXPIRED_SQL = f"""
    UPDATE lot_prices SET synced_at = '{SKIPPED}'
    WHERE origin = '{ORIGIN_LOCAL}' AND synced_at IS NULL AND captured_at < ?"""
INSERT_REMOTE_SQL = f"""
    INSERT OR IGNORE INTO lot_prices
        (item_id, server, lot_size, price, captured_at, origin, synced_at, source_key_id)
    VALUES (?, ?, ?, ?, ?, '{ORIGIN_REMOTE}', ?, ?)"""


class PendingReading(NamedTuple):
    """One local price still to send: its row number and the data that goes on the wire."""

    row_id: int
    item_id: int
    server: str
    lot_size: int
    price: int
    captured_at: str


def mark_sent(connection: sqlite3.Connection, row_ids: Sequence[int], moment: str) -> None:
    """Record that these rows reached the server (or were left out as redundant)."""
    with connection:
        connection.executemany("UPDATE lot_prices SET synced_at = ? WHERE id = ?",
                               [(moment, row_id) for row_id in row_ids])


def _repeats_the_last_sent_price(connection: sqlite3.Connection, row: PendingReading) -> bool:
    """True when the last row really sent for this key has the same price and is less than the resend delay older."""
    last = connection.execute(LAST_SENT_SQL, (row.item_id, row.server, row.lot_size, row.captured_at)).fetchone()
    if last is None or last[0] != row.price:
        return False
    elapsed = datetime.strptime(row.captured_at, DATE_FORMAT) - datetime.strptime(last[1], DATE_FORMAT)
    return elapsed <= timedelta(seconds=MIN_RESEND_SECONDS)


def _not_worth_sending(connection: sqlite3.Connection, row: PendingReading) -> bool:
    """A row the server would refuse, or one that only repeats the last sent price."""
    values_ok = valid_price_data(row.item_id, row.server, row.lot_size, row.price)
    return not values_ok or _repeats_the_last_sent_price(connection, row)


def pending_readings(connection: sqlite3.Connection, limit: int, now: datetime | None = None) -> list[PendingReading]:
    """The oldest local rows worth sending (at most `limit`); expired, invalid and repeated rows are marked skipped."""
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=SEND_MAX_AGE_DAYS)).strftime(DATE_FORMAT)
    with connection:
        connection.execute(EXPIRED_SQL, (cutoff,))
    wanted, skipped = [], []
    for values in connection.execute(UNSENT_SQL).fetchall():
        row = PendingReading(*values)
        if len(wanted) == limit:
            break
        (skipped if _not_worth_sending(connection, row) else wanted).append(row)
    with connection:
        connection.executemany(f"UPDATE lot_prices SET synced_at = '{SKIPPED}' WHERE id = ?",
                               [(row.row_id,) for row in skipped])
    return wanted


def insert_remote(connection: sqlite3.Connection, readings: Sequence[Mapping[str, object]], moment: str) -> int:
    """Store readings received from other players (marked remote and already synced); returns the new rows."""
    before = connection.total_changes
    with connection:
        connection.executemany(INSERT_REMOTE_SQL, [
            (item["item_id"], item["server"], item["lot_size"], item["price"], item["observed_at"], moment,
             item["key_id"]) for item in readings])
    return connection.total_changes - before


def get_state(connection: sqlite3.Connection, name: str) -> str | None:
    """A saved synchronisation value (cursor...), or None."""
    row = connection.execute("SELECT value FROM sync_state WHERE name = ?", (name,)).fetchone()
    return row[0] if row else None


def set_state(connection: sqlite3.Connection, name: str, value: str) -> None:
    """Save a synchronisation value."""
    with connection:
        connection.execute("INSERT INTO sync_state (name, value) VALUES (?, ?) "
                           "ON CONFLICT(name) DO UPDATE SET value = excluded.value", (name, value))


def clear_state(connection: sqlite3.Connection, *names: str) -> None:
    """Forget saved synchronisation values."""
    with connection:
        connection.executemany("DELETE FROM sync_state WHERE name = ?", [(name,) for name in names])
