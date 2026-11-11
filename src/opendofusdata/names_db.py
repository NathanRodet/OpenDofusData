"""Item reference data inside the SQLite database: import and gap queries."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from opendofusdata.game_servers import GameServer
from opendofusdata.item_names import ItemEntry

INSERT_ITEM_SQL = "INSERT INTO items (item_id, name_fr, level, type_fr) VALUES (?, ?, ?, ?)"
INSERT_SERVER_SQL = ("INSERT INTO servers (server_id, name_fr, game_type_id, game_type_fr, "
                     "community_id) VALUES (?, ?, ?, ?, ?)")


@dataclass(frozen=True)
class UnknownItem:
    """An item id seen in prices or statistics but absent from the reference table."""

    item_id: int
    lot_price_rows: int
    stats_rows: int
    first_seen: str
    last_seen: str

    @property
    def row_count(self) -> int:
        """Total number of captured rows for this id."""
        return self.lot_price_rows + self.stats_rows


def _replace_servers(connection: sqlite3.Connection, servers: Iterable[GameServer]) -> None:
    rows = ((server.server_id, server.name, server.game_type_id, server.game_type,
             server.community_id) for server in servers)
    connection.execute("DELETE FROM servers")
    connection.executemany(INSERT_SERVER_SQL, rows)


def replace_items(connection: sqlite3.Connection, entries: Iterable[ItemEntry],
                  servers: Iterable[GameServer] | None = None) -> int:
    """Replace items (and servers, when given) in one transaction; roll back on any error."""
    rows = ((entry.item_id, entry.name, entry.level, entry.type_name) for entry in entries)
    with connection:
        connection.execute("DELETE FROM items")
        connection.executemany(INSERT_ITEM_SQL, rows)
        if servers is not None:
            _replace_servers(connection, servers)
        return connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def count_servers(connection: sqlite3.Connection) -> int:
    """Return the number of rows of the servers table."""
    return connection.execute("SELECT COUNT(*) FROM servers").fetchone()[0]


def count_items(connection: sqlite3.Connection) -> int:
    """Return the number of rows of the reference table."""
    return connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def unknown_items(connection: sqlite3.Connection) -> list[UnknownItem]:
    """Return every item id missing from the reference table, by id."""
    return [UnknownItem(*row) for row in connection.execute("SELECT * FROM unknown_items")]
