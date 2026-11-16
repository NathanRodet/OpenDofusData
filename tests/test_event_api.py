"""The event calls: what is sent, and the answers the client refuses (the server is not trusted blindly)."""

import pytest

from opendofusdata import event_api
from opendofusdata.event_kinds import BROKEN, PET
from opendofusdata.sync_api import SyncFailure

BASE = "https://sync.exemple.fr"
KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"


def good(seq: int = 4) -> dict[str, object]:
    return {"seq": seq, "key_id": "BBBBBBBBBBB", "server": "Brial", "item_id": 1, "quantity": 2, "coefficient": 0.5,
            "runes": [[10, 3]], "observed_at": "2026-11-15T09:00:00Z"}


class FakeCall:
    def __init__(self, answer: dict[str, object]) -> None:
        self.answer, self.requests = answer, []

    def __call__(self, base_url, method, path, key, body=None):
        self.requests.append((method, path, body))
        return self.answer


def use(monkeypatch: pytest.MonkeyPatch, answer: dict[str, object]) -> FakeCall:
    fake = FakeCall(answer)
    monkeypatch.setattr(event_api, "call_server", fake)
    return fake


def test_events_are_posted_to_the_route_of_their_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use(monkeypatch, {"accepted": 1, "duplicates": 0})
    assert event_api.push_events(BASE, KEY, BROKEN, [good()]) == 1
    assert fake.requests == [("POST", "/brisages", {"events": [good()]})]


def test_the_feeds_ask_for_a_page_after_a_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use(monkeypatch, {"events": [good(5)], "next": 5})
    assert event_api.pull_event_changes(BASE, KEY, BROKEN, 3) == ([good(5)], 5)
    fake.answer = {"events": [], "next": 7}
    event_api.pull_event_own(BASE, KEY, PET, 7)
    assert [path for _, path, _ in fake.requests] == ["/brisages?since=3&limit=2000", "/familiers/mine?after=7&limit=2000"]


@pytest.mark.parametrize("answer", [
    {"events": "x", "next": 1}, {"events": [], "next": -1}, {"events": [], "next": True}, {"next": 1},
    {"events": [{**good(), "quantity": 0}], "next": 4}, {"events": [{**good(), "key_id": "short"}], "next": 4},
    {"events": [{**good(), "observed_at": "yesterday"}], "next": 4}, {"events": [{**good(), "seq": "4"}], "next": 4},
    {"events": ["x"], "next": 4},
])
def test_an_odd_answer_is_refused(monkeypatch: pytest.MonkeyPatch, answer: dict[str, object]) -> None:
    use(monkeypatch, answer)
    with pytest.raises(SyncFailure):
        event_api.pull_event_changes(BASE, KEY, BROKEN, 0)


def test_a_non_numeric_accepted_count_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, {"accepted": "1"})
    with pytest.raises(SyncFailure):
        event_api.push_events(BASE, KEY, BROKEN, [good()])
