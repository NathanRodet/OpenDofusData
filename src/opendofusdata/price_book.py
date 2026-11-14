"""The latest known prices of every item of one server, read from the database."""

import json
import sqlite3
from bisect import bisect_right
from datetime import datetime

from opendofusdata.price_rules import SINGLE_UNIT_LOT, ItemPrices, unit_price
from opendofusdata.timeutil import format_utc

HISTORY_LIMIT = 500
STATS_PERIOD_24H = "24h"
LATEST_LOTS_SQL = """
    SELECT item_id, lot_size, price, captured_at FROM (
        SELECT item_id, lot_size, price, captured_at, ROW_NUMBER() OVER (
            PARTITION BY item_id, lot_size ORDER BY captured_at DESC, id DESC) AS rank
        FROM lot_prices WHERE server = ?) WHERE rank = 1"""
LATEST_STATS_SQL = """
    SELECT item_id, median, mean FROM (
        SELECT item_id, median, mean, ROW_NUMBER() OVER (
            PARTITION BY item_id ORDER BY captured_at DESC, id DESC) AS rank
        FROM market_stats WHERE server = ? AND period = ?) WHERE rank = 1"""
CURVE_PERIODS = ("24h", "7d")
LAST_CURVE_SQL = """
    SELECT points_json FROM market_stats WHERE server = ? AND item_id = ? AND period = ?
    ORDER BY captured_at DESC, id DESC LIMIT 1"""
HISTORY_SQL = """
    SELECT captured_at, price FROM lot_prices WHERE server = ? AND item_id = ? AND lot_size = ?
    ORDER BY captured_at DESC, id DESC LIMIT ?"""


class PriceBook:
    """Latest prices per item for one server; the lot x1 history is loaded per item when asked."""

    def __init__(self, connection: sqlite3.Connection, server: str, prices: dict[int, ItemPrices]) -> None:
        self._connection = connection
        self._server = server
        self._prices = prices
        self._histories: dict[int, tuple[list[str], list[int]]] = {}

    @classmethod
    def load(cls, connection: sqlite3.Connection, server: str) -> "PriceBook":
        """Read the latest lot prices and 24 h statistics; sqlite3.Error is left to the caller."""
        lots: dict[int, dict[int, int]] = {}
        seen: dict[int, str] = {}
        lot_seen: dict[int, dict[int, str]] = {}
        for item_id, lot_size, price, captured_at in connection.execute(LATEST_LOTS_SQL, (server,)):
            lots.setdefault(item_id, {})[lot_size] = price
            lot_seen.setdefault(item_id, {})[lot_size] = captured_at
            seen[item_id] = max(seen.get(item_id, captured_at), captured_at)
        stats = {item_id: (median, mean) for item_id, median, mean
                 in connection.execute(LATEST_STATS_SQL, (server, STATS_PERIOD_24H))}
        prices = {item_id: ItemPrices(lots.get(item_id, {}), *stats.get(item_id, (None, None)), seen.get(item_id),
                                      lot_seen.get(item_id, {}))
                  for item_id in lots.keys() | stats.keys()}
        return cls(connection, server, prices)

    def prices_of(self, item_id: int) -> ItemPrices | None:
        """What is known of the item, or None."""
        return self._prices.get(item_id)

    def seen_at(self, item_id: int) -> str | None:
        """The stored time of the newest lot price of the item, or None."""
        prices = self._prices.get(item_id)
        return None if prices is None else prices.seen_at

    def unit_price(self, item_id: int, mode: str) -> float | None:
        """The unit price of the item under the price mode."""
        return unit_price(self.prices_of(item_id), mode)

    def last_sale(self, item_id: int) -> float | None:
        """The price of the last point of the market curve (24 h, else 7 d): what the game shows on hover."""
        for period in CURVE_PERIODS:
            row = self._connection.execute(LAST_CURVE_SQL, (self._server, item_id, period)).fetchone()
            points = json.loads(row[0]) if row else []
            if points:
                return float(points[-1][1])
        return None

    def price_at(self, item_id: int, moment: datetime) -> float | None:
        """The lot x1 price captured at or before the moment, or None."""
        moments, prices = self._history_of(item_id)
        position = bisect_right(moments, format_utc(moment))
        return float(prices[position - 1]) if position else None

    def _history_of(self, item_id: int) -> tuple[list[str], list[int]]:
        if item_id not in self._histories:
            rows = self._connection.execute(
                HISTORY_SQL, (self._server, item_id, SINGLE_UNIT_LOT, HISTORY_LIMIT)).fetchall()
            rows.reverse()
            self._histories[item_id] = ([moment for moment, _ in rows], [price for _, price in rows])
        return self._histories[item_id]
