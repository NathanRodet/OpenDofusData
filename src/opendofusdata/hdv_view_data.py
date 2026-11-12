"""What the HDV page shows, read from the database: one row per item and one detail per item."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from opendofusdata.item_labels import ItemLabeler, ItemTyper
from opendofusdata.price_book import STATS_PERIOD_24H, PriceBook
from opendofusdata.price_rules import SINGLE_UNIT_LOT
from opendofusdata.records import MARKET_PERIODS, LotPrice
from opendofusdata.time_filters import Window, parse_stored, stored_bounds

HISTORY_LIMIT = 500
SEEN_SQL = """
    SELECT item_id, MAX(captured_at) FROM (
        SELECT item_id, captured_at FROM lot_prices WHERE server = :server AND captured_at BETWEEN :low AND :high
        UNION ALL
        SELECT item_id, captured_at FROM market_stats WHERE server = :server AND captured_at BETWEEN :low AND :high)
    GROUP BY item_id"""
LATEST_STATS_SQL = """
    SELECT item_id, median, sold_count FROM (
        SELECT item_id, median, sold_count, ROW_NUMBER() OVER (
            PARTITION BY item_id ORDER BY captured_at DESC, id DESC) AS rank
        FROM market_stats WHERE server = ? AND period = ?) WHERE rank = 1"""
DETAIL_STATS_SQL = """
    SELECT period, median, mean, sold_count, points_json FROM market_stats
    WHERE server = ? AND item_id = ? ORDER BY captured_at, id"""
DETAIL_LOTS_SQL = """
    SELECT lot_size, price FROM (
        SELECT lot_size, price, ROW_NUMBER() OVER (
            PARTITION BY lot_size ORDER BY captured_at DESC, id DESC) AS rank
        FROM lot_prices WHERE server = ? AND item_id = ?) WHERE rank = 1"""
HISTORY_SQL = """
    SELECT item_id, server, lot_size, price, captured_at FROM lot_prices
    WHERE server = ? AND item_id = ? ORDER BY captured_at DESC, id DESC LIMIT ?"""


@dataclass(frozen=True)
class HdvRow:
    """One item of the HDV table."""

    item_id: int
    name: str
    type_name: str
    last_price: int | None
    median_24h: int | None
    sold_24h: int | None
    last_seen: datetime


@dataclass(frozen=True)
class CurvePoint:
    """One point of a market price curve."""

    moment: datetime
    price: int
    quantity: int


@dataclass(frozen=True)
class HdvDetail:
    """Everything the detail panel of one item shows."""

    item_id: int
    name: str
    type_name: str
    stats: dict[str, tuple[int, int, int]]
    curves: dict[str, list[CurvePoint]]
    lots: dict[int, int]
    history: list[LotPrice]


def hdv_rows(connection: sqlite3.Connection, server: str, window: Window,
             name_of: ItemLabeler, type_of: ItemTyper) -> list[HdvRow]:
    """The items captured inside the window, with their latest price and 24 h statistics."""
    low, high = stored_bounds(window)
    seen = connection.execute(SEEN_SQL, {"server": server, "low": low, "high": high}).fetchall()
    book = PriceBook.load(connection, server)
    stats = {item_id: (median, sold) for item_id, median, sold
             in connection.execute(LATEST_STATS_SQL, (server, STATS_PERIOD_24H))}
    rows = []
    for item_id, last_seen in seen:
        prices = book.prices_of(item_id)
        median, sold = stats.get(item_id, (None, None))
        rows.append(HdvRow(item_id, name_of(item_id), type_of(item_id),
                           prices.lots.get(SINGLE_UNIT_LOT) if prices else None, median, sold,
                           parse_stored(last_seen)))
    return sorted(rows, key=lambda row: row.last_seen, reverse=True)


def _curve(points_json: str) -> list[CurvePoint]:
    points = [CurvePoint(datetime.fromtimestamp(seconds, timezone.utc), price, quantity)
              for seconds, price, quantity in json.loads(points_json)]
    return sorted(points, key=lambda point: point.moment)


def hdv_detail(connection: sqlite3.Connection, server: str, item_id: int,
               name_of: ItemLabeler, type_of: ItemTyper) -> HdvDetail:
    """The statistics, curves, latest lots and price history of one item (empty when nothing is stored)."""
    stats, curves = {}, {}
    for period, median, mean, sold, points_json in connection.execute(DETAIL_STATS_SQL, (server, item_id)):
        if period in MARKET_PERIODS:
            stats[period], curves[period] = (median, mean, sold), _curve(points_json)
    lots = dict(connection.execute(DETAIL_LOTS_SQL, (server, item_id)).fetchall())
    history = [LotPrice(*row) for row in connection.execute(HISTORY_SQL, (server, item_id, HISTORY_LIMIT))]
    return HdvDetail(item_id, name_of(item_id), type_of(item_id), stats, curves, lots, history)
