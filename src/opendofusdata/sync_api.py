"""The network calls of the synchronisation: send prices, fetch the other players' prices (nothing secret in errors)."""

import re
from collections.abc import Sequence
from typing import NamedTuple

from opendofusdata.https_json import HttpsFailure, request_json
from opendofusdata.sync_client import FAILURE_MESSAGES, HTTP_OK, HTTP_UNAUTHORIZED, REFUSED_MESSAGE, UNEXPECTED_MESSAGE
from opendofusdata.sync_rules import is_whole_number, valid_cursor, valid_price_data
from opendofusdata.sync_store import PendingReading

SYNC_MAX_RESPONSE_BYTES = 1_048_576
SYNC_PAGE_SIZE = 2000
HTTP_UNPROCESSABLE = 422
REJECTED_MESSAGE = "Le serveur a refusé des relevés (vérifie l'heure de ton PC)"
READINGS_PATH = "/readings"
MINE_PATH = "/readings/mine"
LATEST_PATH = "/readings/latest"
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SyncFailure(Exception):
    """A synchronisation call failed; `refused` is True when the server rejected the key. Never contains the key."""

    def __init__(self, message: str, refused: bool = False) -> None:
        super().__init__(message)
        self.refused = refused


class LatestPage(NamedTuple):
    """One page of the latest-price snapshot: the readings, the next cursor, the starting point and the end flag."""

    readings: list[dict[str, object]]
    next: int
    as_of: int
    done: bool


def _valid_reading(item: object) -> bool:
    """True for a reading with exactly the expected field types and values (the server is not trusted blindly)."""
    return (isinstance(item, dict)
            and valid_price_data(item.get("item_id"), item.get("server"), item.get("lot_size"), item.get("price"))
            and isinstance(item.get("key_id"), str) and KEY_ID_PATTERN.fullmatch(item["key_id"]) is not None
            and isinstance(item.get("observed_at"), str) and DATE_PATTERN.fullmatch(item["observed_at"]) is not None)


def _call(base_url: str, method: str, path: str, key: str, body: dict[str, object] | None = None) -> dict[str, object]:
    """One authenticated request; raises SyncFailure for a refused key, a network problem or an odd answer."""
    try:
        status, answer = request_json(base_url, method, path, token=key, body=body,
                                      max_response_bytes=SYNC_MAX_RESPONSE_BYTES)
    except HttpsFailure as failure:
        raise SyncFailure(FAILURE_MESSAGES.get(failure.reason, UNEXPECTED_MESSAGE)) from None
    if status == HTTP_UNAUTHORIZED:
        raise SyncFailure(REFUSED_MESSAGE, refused=True)
    if status == HTTP_UNPROCESSABLE:
        raise SyncFailure(REJECTED_MESSAGE)
    if status != HTTP_OK:
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return answer


def _readings_and_next(answer: dict[str, object]) -> tuple[list[dict[str, object]], int]:
    readings, following = answer.get("readings"), answer.get("next")
    if not isinstance(readings, list) or not valid_cursor(following) or not all(map(_valid_reading, readings)):
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return readings, following


def push_readings(base_url: str, key: str, readings: Sequence[PendingReading]) -> int:
    """Send these readings; returns how many the server accepted (the others were known already)."""
    body = {"readings": [{"server": item.server, "item_id": item.item_id, "lot_size": item.lot_size,
                          "price": item.price, "observed_at": item.captured_at} for item in readings]}
    accepted = _call(base_url, "POST", READINGS_PATH, key, body).get("accepted")
    if not is_whole_number(accepted):
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return accepted


def pull_changes(base_url: str, key: str, since: int) -> tuple[list[dict[str, object]], int]:
    """The other players' readings after order number `since`, and the cursor to continue from."""
    answer = _call(base_url, "GET", f"{READINGS_PATH}?since={since}&limit={SYNC_PAGE_SIZE}", key)
    return _readings_and_next(answer)


def pull_latest_page(base_url: str, key: str, after: int) -> LatestPage:
    """One page of the latest price of every (server, item, lot) among the other players."""
    answer = _call(base_url, "GET", f"{LATEST_PATH}?after={after}&limit={SYNC_PAGE_SIZE}", key)
    readings, following = _readings_and_next(answer)
    as_of, done = answer.get("as_of"), answer.get("done")
    if not valid_cursor(as_of) or not isinstance(done, bool):
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return LatestPage(readings, following, as_of, done)


def pull_own_page(base_url: str, key: str, after: int) -> tuple[list[dict[str, object]], int]:
    """One page of the readings this key sent itself (restoring a player's history on a new database)."""
    answer = _call(base_url, "GET", f"{MINE_PATH}?after={after}&limit={SYNC_PAGE_SIZE}", key)
    return _readings_and_next(answer)
