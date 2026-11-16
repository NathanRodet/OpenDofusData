"""The bounds the sync server enforces, mirrored here so the client never sends or stores what it would refuse.

They are copied from src/server/keyserver/schemas.py (the client never imports server code).
"""

import re
import unicodedata

LOT_SIZES = (1, 10, 100, 1000)
MAX_ITEM_ID = 10_000_000
MAX_PRICE = 1_000_000_000_000
MAX_CURSOR = 999_999_999_999  # twelve digits, the most a query parameter may carry
# A letter or digit (accents included), then letters, digits, spaces, hyphens or underscores.
SERVER_NAME_PATTERN = re.compile(r"^[^\W_][\w -]{0,39}$")
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def is_whole_number(value: object) -> bool:
    """True for an int that is not a boolean."""
    return isinstance(value, int) and not isinstance(value, bool)


def valid_server_name(name: object) -> bool:
    """A plain game server name: no leading symbol (so no spreadsheet formula), no invisible or trailing blank."""
    if not isinstance(name, str) or SERVER_NAME_PATTERN.fullmatch(name) is None or name != name.rstrip():
        return False
    return not any(unicodedata.category(character) in INVISIBLE_CATEGORIES for character in name)


def valid_price_data(item_id: object, server: object, lot_size: object, price: object) -> bool:
    """True when these values would pass the server's schema."""
    return (is_whole_number(item_id) and 1 <= item_id <= MAX_ITEM_ID and lot_size in LOT_SIZES
            and is_whole_number(lot_size) and is_whole_number(price) and 1 <= price <= MAX_PRICE
            and valid_server_name(server))


def valid_cursor(value: object) -> bool:
    """True for a whole number a query parameter can carry."""
    return is_whole_number(value) and 0 <= value <= MAX_CURSOR
