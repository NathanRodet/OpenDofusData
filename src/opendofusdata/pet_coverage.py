"""How many resources of the pet food categories have a known experience coefficient, and which ones do not."""

import logging
import sqlite3
from collections.abc import Collection, Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ITEMS_SQL = "SELECT item_id, name_fr, type_fr FROM items"
ItemRecord = tuple[int, str, str]  # item id, French name, category


@dataclass(frozen=True)
class MissingItem:
    """A resource of a known pet food category whose experience coefficient is still unknown."""

    item_id: int
    name: str
    category: str


@dataclass(frozen=True)
class Coverage:
    """`covered` resources with a coefficient out of `total` possible, and the `missing` ones."""

    covered: int
    total: int
    missing: tuple[MissingItem, ...]

    def categories(self) -> list[str]:
        """The categories that still have missing resources, sorted."""
        return sorted({item.category for item in self.missing})


def build_coverage(items: Iterable[ItemRecord], covered_ids: Collection[int]) -> Coverage:
    """The possible resources are the items of every category that holds a resource with a known coefficient."""
    records = list(items)
    categories = {category for item_id, _, category in records if item_id in covered_ids and category}
    universe = [record for record in records if record[2] in categories]
    missing = sorted((MissingItem(*record) for record in universe if record[0] not in covered_ids),
                     key=lambda item: item.name.casefold())
    return Coverage(len(universe) - len(missing), len(universe), tuple(missing))


def load_coverage(connection: sqlite3.Connection, covered_ids: Collection[int]) -> Coverage:
    """The coverage computed from the `items` table; empty when the table is missing."""
    try:
        records = connection.execute(ITEMS_SQL).fetchall()
    except sqlite3.OperationalError as error:
        logger.info("table des objets absente, couverture vide (%s)", error)
        return Coverage(0, 0, ())
    return build_coverage(records, covered_ids)
