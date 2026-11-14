"""Search items by name in the `items` table (read-only), ignoring case and accents."""

import sqlite3
import unicodedata

SEARCH_LIMIT = 12
FOLD_FUNCTION = "fold_text"
SEARCH_SQL = (f"SELECT item_id, name_fr FROM items WHERE {FOLD_FUNCTION}(name_fr) LIKE ? ESCAPE '\\' "
              "ORDER BY name_fr LIMIT ?")


def fold_text(text: str | None) -> str:
    """The text lowercased and without accents, so "Épée" and "epee" compare equal."""
    decomposed = unicodedata.normalize("NFD", (text or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def search_items(connection: sqlite3.Connection, text: str, limit: int = SEARCH_LIMIT) -> list[tuple[int, str]]:
    """The items whose French name contains the text, in name order; empty when the table is missing."""
    cleaned = fold_text(text.strip())
    if not cleaned:
        return []
    pattern = "%" + cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    connection.create_function(FOLD_FUNCTION, 1, fold_text, deterministic=True)
    try:
        return [(item_id, name) for item_id, name in connection.execute(SEARCH_SQL, (pattern, limit))]
    except sqlite3.OperationalError:
        return []
