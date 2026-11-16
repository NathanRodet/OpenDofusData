"""The network calls of the shared events: send ours, fetch the other players', fetch our own history."""

from collections.abc import Mapping, Sequence

from opendofusdata.event_kinds import EventKind
from opendofusdata.sync_api import DATE_PATTERN, KEY_ID_PATTERN, SYNC_PAGE_SIZE, SyncFailure, call_server
from opendofusdata.sync_client import UNEXPECTED_MESSAGE
from opendofusdata.sync_rules import is_whole_number, valid_cursor

MINE_SUFFIX = "/mine"


def _valid_event(kind: EventKind, item: object) -> bool:
    """True for an event with the expected shape and values (the server is not trusted blindly)."""
    return (isinstance(item, dict) and is_whole_number(item.get("seq"))
            and isinstance(item.get("key_id"), str) and KEY_ID_PATTERN.fullmatch(item["key_id"]) is not None
            and isinstance(item.get("observed_at"), str) and DATE_PATTERN.fullmatch(item["observed_at"]) is not None
            and kind.valid(item))


def _events_and_next(kind: EventKind, answer: Mapping[str, object]) -> tuple[list[dict[str, object]], int]:
    events, following = answer.get("events"), answer.get("next")
    if not isinstance(events, list) or not valid_cursor(following) or not all(_valid_event(kind, item) for item in events):
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return events, following


def push_events(base_url: str, key: str, kind: EventKind, events: Sequence[Mapping[str, object]]) -> int:
    """Send these events; returns how many the server accepted (the others were known already)."""
    accepted = call_server(base_url, "POST", kind.path, key, {"events": list(events)}).get("accepted")
    if not is_whole_number(accepted):
        raise SyncFailure(UNEXPECTED_MESSAGE)
    return accepted


def pull_event_changes(base_url: str, key: str, kind: EventKind, since: int) -> tuple[list[dict[str, object]], int]:
    """The other players' events after order number `since`, and the cursor to continue from."""
    return _events_and_next(kind, call_server(base_url, "GET", f"{kind.path}?since={since}&limit={SYNC_PAGE_SIZE}", key))


def pull_event_own(base_url: str, key: str, kind: EventKind, after: int) -> tuple[list[dict[str, object]], int]:
    """One page of the events this key sent itself (restoring a player's history on a new database)."""
    path = f"{kind.path}{MINE_SUFFIX}?after={after}&limit={SYNC_PAGE_SIZE}"
    return _events_and_next(kind, call_server(base_url, "GET", path, key))
