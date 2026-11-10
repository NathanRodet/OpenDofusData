"""SQLite storage for HDV prices, with a writer thread keeping capture off the disk."""

import json
import logging
import queue
import sqlite3
import threading
from collections.abc import Iterator

from dofus_prices.records import LotPrice, MarketStats

logger = logging.getLogger(__name__)

LOT_SIZES = (1, 10, 100, 1000)
MARKET_PERIODS = ("24h", "7d", "30d")
WRITER_JOIN_TIMEOUT_SECONDS = 30.0

SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS lot_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, server TEXT NOT NULL,
        lot_size INTEGER NOT NULL, price INTEGER NOT NULL, captured_at TEXT NOT NULL)""",
    """CREATE INDEX IF NOT EXISTS idx_lot_prices_lookup
        ON lot_prices (item_id, server, lot_size, captured_at, id)""",
    """CREATE TABLE IF NOT EXISTS market_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, server TEXT NOT NULL,
        period TEXT NOT NULL, points_json TEXT NOT NULL, median INTEGER NOT NULL,
        mean INTEGER NOT NULL, sold_count INTEGER NOT NULL, server_updated_at TEXT NOT NULL,
        last_purchase_at TEXT NOT NULL, captured_at TEXT NOT NULL)""",
    """CREATE INDEX IF NOT EXISTS idx_market_stats_lookup
        ON market_stats (item_id, period, captured_at, id)""",
)
LOT_COLUMNS = "item_id, server, lot_size, price, captured_at"
STATS_COLUMNS = (
    "item_id, server, period, points_json, median, mean, sold_count, "
    "server_updated_at, last_purchase_at, captured_at"
)
LATEST_LOTS_SQL = f"""
    SELECT {LOT_COLUMNS} FROM (
        SELECT {LOT_COLUMNS}, ROW_NUMBER() OVER (
            PARTITION BY item_id, server, lot_size ORDER BY captured_at DESC, id DESC) AS rank
        FROM lot_prices WHERE (:item_id IS NULL OR item_id = :item_id))
    WHERE rank = 1 ORDER BY item_id, server, lot_size"""


class PriceStore:
    """Append-only SQLite history of lot prices and market statistics."""

    def __init__(self, path: str) -> None:
        connection = sqlite3.connect(path)
        try:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()
        except sqlite3.Error:
            connection.close()
            raise
        self._connection: sqlite3.Connection | None = connection

    def save_lot_price(self, lot: LotPrice) -> None:
        """Append a lot price; raise ValueError if the lot size is not allowed."""
        if lot.lot_size not in LOT_SIZES:
            raise ValueError(f"lot_size {lot.lot_size} not in {LOT_SIZES}")
        self._insert(f"INSERT INTO lot_prices ({LOT_COLUMNS}) VALUES (?, ?, ?, ?, ?)",
                     (lot.item_id, lot.server, lot.lot_size, lot.price, lot.captured_at))

    def save_market_stats(self, stats: MarketStats) -> None:
        """Append market statistics; raise ValueError if the period is not allowed."""
        if stats.period not in MARKET_PERIODS:
            raise ValueError(f"period {stats.period!r} not in {MARKET_PERIODS}")
        row = (stats.item_id, stats.server, stats.period, json.dumps(stats.points), stats.median,
               stats.mean, stats.sold_count, stats.server_updated_at, stats.last_purchase_at,
               stats.captured_at)
        self._insert(f"INSERT INTO market_stats ({STATS_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)

    def latest_prices(self, item_id: int | None = None) -> list[LotPrice]:
        """Return the most recent price per (item, server, lot size)."""
        rows = self._open().execute(LATEST_LOTS_SQL, {"item_id": item_id})
        return [LotPrice(*row) for row in rows]

    def price_history(self, item_id: int, lot_size: int) -> list[LotPrice]:
        """Return every capture of an item at a lot size, oldest first."""
        rows = self._open().execute(
            f"SELECT {LOT_COLUMNS} FROM lot_prices WHERE item_id = ? AND lot_size = ? "
            "ORDER BY captured_at, id", (item_id, lot_size))
        return [LotPrice(*row) for row in rows]

    def iter_lot_prices(self) -> Iterator[LotPrice]:
        """Yield every lot price, oldest first."""
        rows = self._open().execute(f"SELECT {LOT_COLUMNS} FROM lot_prices ORDER BY captured_at, id")
        yield from (LotPrice(*row) for row in rows)

    def market_stats_history(self, item_id: int, period: str) -> list[MarketStats]:
        """Return stored market statistics for an item and period, oldest first."""
        rows = self._open().execute(
            f"SELECT {STATS_COLUMNS} FROM market_stats WHERE item_id = ? AND period = ? "
            "ORDER BY captured_at, id", (item_id, period))
        return [_stats_from_row(row) for row in rows]

    def close(self) -> None:
        """Close the connection; safe to call more than once."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _open(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("PriceStore is closed")
        return self._connection

    def _insert(self, statement: str, values: tuple) -> None:
        self._open().execute(statement, values)
        self._open().commit()


def _stats_from_row(row: tuple) -> MarketStats:
    return MarketStats(*row[:3], [tuple(point) for point in json.loads(row[3])], *row[4:])


class StoreWriter:
    """Saves submitted records from a daemon thread owning its own PriceStore.

    Single-producer contract: call submit() from one thread only. Callers must
    call stop() to flush the queue and close the database.
    """

    def __init__(self, store_path: str) -> None:
        self._store_path = store_path
        self._queue: queue.Queue[LotPrice | MarketStats | None] = queue.Queue()
        self._stopped, self._open_error = False, None
        self._opened = threading.Event()
        self._thread = threading.Thread(target=self._run, name="store-writer", daemon=True)
        self._thread.start()
        self._opened.wait()
        if self._open_error is not None:
            self._thread.join()
            raise self._open_error

    def submit(self, record: LotPrice | MarketStats) -> None:
        """Queue a record for saving without blocking; raise RuntimeError after stop()."""
        if self._stopped:
            raise RuntimeError("StoreWriter is stopped")
        self._queue.put(record)

    def stop(self) -> None:
        """Process everything already queued, close the store and join the thread."""
        if not self._stopped:
            self._stopped = True
            self._queue.put(None)
        self._thread.join(WRITER_JOIN_TIMEOUT_SECONDS)
        if self._thread.is_alive():
            logger.warning("Store writer thread still running after %s seconds", WRITER_JOIN_TIMEOUT_SECONDS)

    def _run(self) -> None:
        try:
            store = PriceStore(self._store_path)
        except sqlite3.Error as error:
            logger.exception("Cannot open price database %s", self._store_path)
            self._open_error = error
            return
        finally:
            self._opened.set()
        try:
            while (record := self._queue.get()) is not None:
                self._save(store, record)
        finally:
            store.close()

    @staticmethod
    def _save(store: PriceStore, record: LotPrice | MarketStats) -> None:
        # Broad catch on purpose: this is the thread boundary, the error is logged
        # and the thread must survive to keep saving later records.
        try:
            if isinstance(record, LotPrice):
                store.save_lot_price(record)
            else:
                store.save_market_stats(record)
        except Exception:
            logger.exception("Failed to save record %r", record)
