"""The network calls of the synchronisation: wire format, parsing, refusal and failure messages."""

import pytest

from opendofusdata import sync_api
from opendofusdata.https_json import BAD_RESPONSE, UNREACHABLE, HttpsFailure
from opendofusdata.sync_api import (
    SYNC_MAX_RESPONSE_BYTES, SYNC_PAGE_SIZE, LatestPage, SyncFailure, pull_changes, pull_latest_page, push_readings,
)
from opendofusdata.sync_store import PendingReading

BASE = "https://sync.exemple.fr"
KEY = "odk1.AAAAAAAAAAA.wWDNcTyCnrCij9E3nR2eeRD0iZL3-vFNX-spK0bl7kI"
PENDING = PendingReading(5, 307, "Brial", 10, 5868, "2026-11-16T10:00:00Z")
RECEIVED = {"seq": 3, "key_id": "BBBBBBBBBBB", "server": "Brial", "item_id": 1, "lot_size": 1, "price": 90,
            "observed_at": "2026-11-16T09:00:00Z"}


class Recorder:
    """Stands in for request_json: records the call and answers (or fails) as told."""

    def __init__(self, status: int = 200, answer: dict | None = None, failure: HttpsFailure | None = None) -> None:
        self.status, self.answer, self.failure, self.calls = status, answer or {}, failure, []

    def __call__(self, base_url, method, path, token=None, body=None, **options):
        self.calls.append({"base_url": base_url, "method": method, "path": path, "token": token, "body": body,
                           **options})
        if self.failure:
            raise self.failure
        return self.status, self.answer


def install(monkeypatch: pytest.MonkeyPatch, recorder: Recorder) -> Recorder:
    monkeypatch.setattr(sync_api, "request_json", recorder)
    return recorder


def test_constants() -> None:
    assert (SYNC_MAX_RESPONSE_BYTES, SYNC_PAGE_SIZE) == (1_048_576, 2000)


def test_push_sends_the_wire_format_and_returns_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = install(monkeypatch, Recorder(answer={"accepted": 1, "duplicates": 0}))
    assert push_readings(BASE, KEY, [PENDING]) == 1
    call = recorder.calls[0]
    assert (call["method"], call["path"], call["token"]) == ("POST", "/readings", KEY)
    assert call["body"] == {"readings": [{"server": "Brial", "item_id": 307, "lot_size": 10, "price": 5868,
                                          "observed_at": "2026-11-16T10:00:00Z"}]}
    assert call["max_response_bytes"] == SYNC_MAX_RESPONSE_BYTES


def test_pull_changes_builds_the_query_and_reads_next(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = install(monkeypatch, Recorder(answer={"readings": [RECEIVED], "next": 3}))
    assert pull_changes(BASE, KEY, 2) == ([RECEIVED], 3)
    call = recorder.calls[0]
    assert (call["method"], call["path"], call["body"]) == ("GET", "/readings?since=2&limit=2000", None)


def test_latest_page_parses_done_and_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = install(monkeypatch, Recorder(answer={"readings": [RECEIVED], "next": 3, "as_of": 9, "done": True}))
    assert pull_latest_page(BASE, KEY, 0) == LatestPage([RECEIVED], 3, 9, True)
    assert recorder.calls[0]["path"] == "/readings/latest?after=0&limit=2000"


def test_401_raises_a_refused_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, Recorder(status=401))
    with pytest.raises(SyncFailure) as failure:
        push_readings(BASE, KEY, [PENDING])
    assert failure.value.refused is True


def test_network_failure_raises_a_non_refused_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, Recorder(failure=HttpsFailure(UNREACHABLE)))
    with pytest.raises(SyncFailure) as failure:
        pull_changes(BASE, KEY, 0)
    assert failure.value.refused is False


@pytest.mark.parametrize("answer", [
    {}, {"readings": "x", "next": 1}, {"readings": [], "next": "1"}, {"readings": [{"item_id": 1}], "next": 1},
    {"readings": [{**RECEIVED, "lot_size": 7}], "next": 1}, {"readings": [{**RECEIVED, "price": 0}], "next": 1},
    {"readings": [{**RECEIVED, "observed_at": "hier"}], "next": 1}, {"readings": [{**RECEIVED, "key_id": 5}], "next": 1},
    {"readings": [{**RECEIVED, "item_id": True}], "next": 1},
])
def test_unexpected_body_raises_a_failure(monkeypatch: pytest.MonkeyPatch, answer: dict) -> None:
    install(monkeypatch, Recorder(answer=answer))
    with pytest.raises(SyncFailure):
        pull_changes(BASE, KEY, 0)


def test_unexpected_status_or_push_answer_raises_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, Recorder(status=500))
    with pytest.raises(SyncFailure):
        push_readings(BASE, KEY, [PENDING])
    install(monkeypatch, Recorder(answer={"accepted": "1"}))
    with pytest.raises(SyncFailure):
        push_readings(BASE, KEY, [PENDING])


def test_the_key_never_appears_in_failure_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    for recorder in (Recorder(status=401), Recorder(status=500), Recorder(failure=HttpsFailure(BAD_RESPONSE))):
        install(monkeypatch, recorder)
        with pytest.raises(SyncFailure) as failure:
            push_readings(BASE, KEY, [PENDING])
        assert KEY not in str(failure.value) and KEY.split(".")[1] not in str(failure.value)


def bad_reading(**changes) -> dict:
    return {**RECEIVED, **changes}


@pytest.mark.parametrize("answer", [
    {"readings": [bad_reading(item_id=2**70)], "next": 1}, {"readings": [bad_reading(item_id=10_000_001)], "next": 1},
    {"readings": [bad_reading(price=10**12 + 1)], "next": 1}, {"readings": [bad_reading(price=2**70)], "next": 1},
    {"readings": [], "next": 10**30}, {"readings": [], "next": -1},
    {"readings": [bad_reading(server="=cmd")], "next": 1}, {"readings": [bad_reading(server="+1")], "next": 1},
    {"readings": [bad_reading(server="@x")], "next": 1}, {"readings": [bad_reading(server="Bri\u200bal")], "next": 1},
    {"readings": [bad_reading(server="Brial ")], "next": 1}, {"readings": [bad_reading(server="x" * 41)], "next": 1},
])
def test_hostile_numbers_and_server_names_are_refused(monkeypatch: pytest.MonkeyPatch, answer: dict) -> None:
    install(monkeypatch, Recorder(answer=answer))
    with pytest.raises(SyncFailure):
        pull_changes(BASE, KEY, 0)


def test_latest_page_bounds_as_of_and_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, Recorder(answer={"readings": [], "next": 1, "as_of": 10**30, "done": True}))
    with pytest.raises(SyncFailure):
        pull_latest_page(BASE, KEY, 0)


def test_a_422_says_the_server_refused_the_readings_and_suggests_checking_the_clock(
        monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, Recorder(status=422))
    with pytest.raises(SyncFailure) as failure:
        push_readings(BASE, KEY, [PENDING])
    assert failure.value.refused is False
    assert "heure" in str(failure.value).lower()
