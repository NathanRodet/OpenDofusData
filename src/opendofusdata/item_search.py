"""Search items by name in the `items` table (read-only)."""

import sqlite3

SEARCH_LIMIT = 12
SEARCH_SQL = "SELECT item_id, name_fr FROM items WHERE name_fr LIKE ? ESCAPE '\\' ORDER BY name_fr LIMIT ?"


def search_items(connection: sqlite3.Connection, text: str, limit: int = SEARCH_LIMIT) -> list[tuple[int, str]]:
    """The items whose French name contains the text, in name order; empty when the table is missing."""
    cleaned = text.strip()
    if not cleaned:
        return []
    pattern = "%" + cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    try:
        return [(item_id, name) for item_id, name in connection.execute(SEARCH_SQL, (pattern, limit))]
    except sqlite3.OperationalError:
        return []
