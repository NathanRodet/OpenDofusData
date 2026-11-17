"""The bounds the server enforces on shared events (breakings, pet upgrades), mirrored for the client.

They are copied from src/server/keyserver/event_schemas.py (the client never imports server code).
"""

from collections.abc import Mapping

from opendofusdata.sync_rules import MAX_ITEM_ID, is_whole_number, valid_server_name

MAX_PAIRS = 40
MAX_QUANTITY = 1_000_000_000
MAX_COEFFICIENT = 10.0
MAX_PET_LEVEL = 1000
MAX_EXPERIENCE = 1_000_000_000_000
PET_STATE_FIELDS = {"level": MAX_PET_LEVEL, "experience": MAX_EXPERIENCE, "experience_max": MAX_EXPERIENCE,
                    "prospection": MAX_EXPERIENCE}


def _valid_pair(pair: object) -> bool:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2 or not all(is_whole_number(part) for part in pair):
        return False
    return 1 <= pair[0] <= MAX_ITEM_ID and 1 <= pair[1] <= MAX_QUANTITY


def _valid_pairs(pairs: object, minimum: int = 1) -> bool:
    return isinstance(pairs, (list, tuple)) and minimum <= len(pairs) <= MAX_PAIRS and all(map(_valid_pair, pairs))


def _valid_item_id(value: object) -> bool:
    return is_whole_number(value) and 1 <= value <= MAX_ITEM_ID


def _valid_state(state: object) -> bool:
    if not isinstance(state, Mapping) or set(state) != set(PET_STATE_FIELDS):
        return False
    return all(state[name] is None or (is_whole_number(state[name]) and 0 <= state[name] <= limit)
               for name, limit in PET_STATE_FIELDS.items())


def valid_broken_event(event: Mapping[str, object]) -> bool:
    """True when this broken object would pass the server's schema (the date is checked apart)."""
    coefficient = event.get("coefficient")
    quantity = event.get("quantity")
    return (valid_server_name(event.get("server")) and _valid_item_id(event.get("item_id"))
            and is_whole_number(quantity) and 1 <= quantity <= MAX_QUANTITY
            and isinstance(coefficient, (int, float)) and not isinstance(coefficient, bool)
            and 0 <= coefficient <= MAX_COEFFICIENT and _valid_pairs(event.get("runes"), minimum=0))  # a breaking can give no rune


def valid_pet_event(event: Mapping[str, object]) -> bool:
    """True when this pet upgrade would pass the server's schema (the date is checked apart)."""
    return (valid_server_name(event.get("server")) and _valid_item_id(event.get("pet_item_id"))
            and _valid_pairs(event.get("resources")) and _valid_state(event.get("before"))
            and _valid_state(event.get("after")))
