"""Search items by name in the `items` table (read-only), ignoring case and accents."""

import sqlite3
import unicodedata

SEARCH_LIMIT = 12
FOLD_FUNCTION = "fold_text"
ESCAPE = "\\"  # the LIKE escape character
LIKE = f"{FOLD_FUNCTION}(name_fr) LIKE ? ESCAPE '{ESCAPE}'"
# Best matches first: the exact name, then names starting with the text, then a word starting with it, then the rest.
WORD_SEPARATORS = (" ", "'", "-")
WORD_START = " OR ".join([LIKE] * len(WORD_SEPARATORS))
RANK_SQL = f"CASE WHEN {FOLD_FUNCTION}(name_fr) = ? THEN 0 WHEN {LIKE} THEN 1 WHEN {WORD_START} THEN 2 ELSE 3 END"
SEARCH_SQL = f"SELECT item_id, name_fr FROM items WHERE {LIKE} ORDER BY {RANK_SQL}, name_fr LIMIT ?"


def fold_text(text: str | None) -> str:
    """The text lowercased and without accents, so "Épée" and "epee" compare equal."""
    decomposed = unicodedata.normalize("NFD", (text or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _escape_like(text: str) -> str:
    return text.replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")


def search_items(connection: sqlite3.Connection, text: str, limit: int = SEARCH_LIMIT) -> list[tuple[int, str]]:
    """The items whose French name contains the text, the best matches first; empty when the table is missing."""
    cleaned = fold_text(text.strip())
    if not cleaned:
        return []
    escaped = _escape_like(cleaned)
    word_starts = tuple("%" + separator + escaped + "%" for separator in WORD_SEPARATORS)
    parameters = ("%" + escaped + "%", cleaned, escaped + "%", *word_starts, limit)
    connection.create_function(FOLD_FUNCTION, 1, fold_text, deterministic=True)
    try:
        return [(item_id, name) for item_id, name in connection.execute(SEARCH_SQL, parameters)]
    except sqlite3.OperationalError:
        return []
