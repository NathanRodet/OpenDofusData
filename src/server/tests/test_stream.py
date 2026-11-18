"""The stream: one open connection per key, a frame when something is stored, a heartbeat when it is quiet."""

import threading

import pytest
from fastapi.testclient import TestClient

from helpers import SECRET, authorization
from keyserver import stream_routes
from keyserver.change_notifier import ChangeNotifier, changed_kinds
from keyserver.signed_keys import make_key

ALICE = authorization(make_key(SECRET, "AAAAAAAAAAA"))
BOB = authorization(make_key(SECRET, "BBBBBBBBBBB"))


def test_a_key_holds_one_stream_at_a_time_and_gives_it_back() -> None:
    notifier = ChangeNotifier(max_streams=2)
    assert notifier.open_slot("a") and not notifier.open_slot("a")
    assert notifier.open_slot("b") and not notifier.open_slot("c")  # the server as a whole is full
    notifier.close_slot("a")
    assert notifier.open_slot("c")


def test_changed_kinds_names_the_counters_that_moved() -> None:
    notifier = ChangeNotifier()
    before = notifier.snapshot()
    notifier.notify("readings")
    notifier.notify("broken")
    notifier.notify("broken")
    assert changed_kinds(before, notifier.snapshot()) == ["broken", "readings"]
    assert changed_kinds(notifier.snapshot(), notifier.snapshot()) == []


@pytest.fixture
def quick_stream(monkeypatch) -> None:
    monkeypatch.setattr(stream_routes, "CHECK_SECONDS", 0.05)
    monkeypatch.setattr(stream_routes, "MAX_STREAM_SECONDS", 0.8)
    monkeypatch.setattr(stream_routes, "HEARTBEAT_SECONDS", 0.2)


def test_the_stream_needs_a_key(client: TestClient) -> None:
    assert client.get("/stream").status_code == 401


def test_a_stored_reading_wakes_the_stream_and_a_quiet_stream_beats(client: TestClient, quick_stream) -> None:
    body = {"readings": [{"server": "Brial", "item_id": 1, "lot_size": 1, "price": 5,
                          "observed_at": "2099-01-01T00:00:00Z"}]}
    timer = threading.Timer(0.3, lambda: client.post("/readings", json=body, headers=BOB))
    timer.start()
    response = client.get("/stream", headers=ALICE)
    timer.join()
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert "event: ready" in response.text and ": keepalive" in response.text


def test_a_second_stream_of_the_same_key_is_refused_and_the_slot_is_freed_at_the_end(client: TestClient,
                                                                                    quick_stream) -> None:
    first = client.get("/stream", headers=ALICE)
    assert first.status_code == 200
    again = client.get("/stream", headers=ALICE)  # the first one ended: its slot was given back
    assert again.status_code == 200


def test_a_key_that_already_holds_its_stream_gets_a_429(client: TestClient, quick_stream) -> None:
    from keyserver.stream_routes import TOO_MANY_STATUS

    notifier_holder = {}
    original = ChangeNotifier.open_slot

    def refuse(self, key_id: str) -> bool:
        notifier_holder["asked"] = key_id
        return False

    ChangeNotifier.open_slot = refuse  # type: ignore[method-assign]
    try:
        response = client.get("/stream", headers=ALICE)
    finally:
        ChangeNotifier.open_slot = original  # type: ignore[method-assign]
    assert response.status_code == TOO_MANY_STATUS and notifier_holder["asked"] == "AAAAAAAAAAA"


def test_a_slot_that_was_never_given_back_expires(monkeypatch) -> None:
    from keyserver import change_notifier

    notifier = ChangeNotifier()
    assert notifier.open_slot("a") and not notifier.open_slot("a")
    real = change_notifier.time.monotonic
    monkeypatch.setattr(change_notifier.time, "monotonic", lambda: real() + change_notifier.SLOT_LIFETIME_SECONDS + 1)
    assert notifier.open_slot("a")
