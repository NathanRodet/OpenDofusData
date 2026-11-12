"""What the Familiers page shows: experience and kamas per resource, and the upgrades behind them."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from opendofusdata.item_labels import ItemLabeler, ItemTyper
from opendofusdata.pet_economy import (
    ResourceExperience, experience_by_resource, experience_per_unit, feeding_gain, is_reliable,
    kamas_per_experience, leveling_cost,
)
from opendofusdata.pets_store import pet_feedings
from opendofusdata.price_book import PriceBook
from opendofusdata.records import PetFeeding
from opendofusdata.time_filters import Window, parse_stored, stored_bounds


@dataclass(frozen=True)
class PetRow:
    """One resource of the Familiers table."""

    item_id: int
    name: str
    type_name: str
    unit_price: float | None
    per_unit: float | None
    kamas_per_xp: float | None
    feedings: int
    last_seen: datetime | None
    cost: float | None
    reliable: bool


@dataclass(frozen=True)
class PetUpgrade:
    """One upgrade in which the resource was given; `mixed` when other resources were given too."""

    moment: datetime
    pet_name: str
    units: int
    gain: int | None
    mixed: bool


@dataclass(frozen=True)
class PetDetail:
    """The detail panel of one resource, over every stored upgrade of the server."""

    row: PetRow
    upgrades: list[PetUpgrade]
    ratio_points: list[tuple[datetime, float, float]]


def _server_feedings(connection: sqlite3.Connection, server: str) -> list[PetFeeding]:
    return [feeding for feeding in pet_feedings(connection) if feeding.server == server]


def _row_of(item_id: int, stats: ResourceExperience | None, last_seen: datetime | None, name_of: ItemLabeler,
            type_of: ItemTyper, book: PriceBook, mode: str) -> PetRow:
    price = book.unit_price(item_id, mode)
    per_unit = experience_per_unit(stats) if stats else None
    ratio = kamas_per_experience(price, per_unit)
    return PetRow(item_id, name_of(item_id), type_of(item_id), price, per_unit, ratio,
                  stats.feedings if stats else 0, last_seen, leveling_cost(ratio), bool(stats and is_reliable(stats)))


def _ratio_order(row: PetRow) -> tuple[bool, float]:
    return (row.kamas_per_xp is None, row.kamas_per_xp or 0.0)


def pet_rows(connection: sqlite3.Connection, server: str, window: Window, name_of: ItemLabeler,
             type_of: ItemTyper, book: PriceBook, mode: str) -> list[PetRow]:
    """One row per resource seen in usable upgrades inside the window, cheapest experience first."""
    low, high = stored_bounds(window)
    feedings = [feeding for feeding in _server_feedings(connection, server) if low <= feeding.captured_at <= high]
    totals = experience_by_resource(feedings)
    seen: dict[int, datetime] = {}
    for feeding in feedings:
        if len(feeding.resources) == 1 and feeding.resources[0][0] in totals:
            seen[feeding.resources[0][0]] = parse_stored(feeding.captured_at)
    rows = [_row_of(item_id, stats, seen.get(item_id), name_of, type_of, book, mode)
            for item_id, stats in totals.items()]
    return sorted(rows, key=_ratio_order)


def _upgrade_of(feeding: PetFeeding, item_id: int, name_of: ItemLabeler) -> PetUpgrade:
    units = next(quantity for resource, quantity in feeding.resources if resource == item_id)
    mixed = len(feeding.resources) > 1
    return PetUpgrade(parse_stored(feeding.captured_at), name_of(feeding.pet_item_id), units,
                      None if mixed else feeding_gain(feeding), mixed)


def _ratio_points(upgrades: list[PetUpgrade], item_id: int, book: PriceBook) -> list[tuple[datetime, float, float]]:
    points = []
    for upgrade in upgrades:
        price = book.price_at(item_id, upgrade.moment)
        if upgrade.gain and price is not None:
            points.append((upgrade.moment, price * upgrade.units / upgrade.gain, price))
    return points


def pet_detail(connection: sqlite3.Connection, server: str, item_id: int, name_of: ItemLabeler,
               type_of: ItemTyper, book: PriceBook, mode: str) -> PetDetail | None:
    """All upgrades that used the resource (newest first); None when it was never used."""
    feedings = [feeding for feeding in _server_feedings(connection, server)
                if any(resource == item_id for resource, _ in feeding.resources)]
    if not feedings:
        return None
    upgrades = sorted((_upgrade_of(feeding, item_id, name_of) for feeding in feedings),
                      key=lambda upgrade: upgrade.moment, reverse=True)
    stats = experience_by_resource(feedings).get(item_id)
    row = _row_of(item_id, stats, upgrades[0].moment, name_of, type_of, book, mode)
    return PetDetail(row, upgrades, _ratio_points(list(reversed(upgrades)), item_id, book))
