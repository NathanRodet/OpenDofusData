"""The routes of the shared events (/brisages, /familiers): send, feed, own history, strict inputs."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from helpers import SECRET, authorization
from keyserver.signed_keys import make_key

ALICE = authorization(make_key(SECRET, "AAAAAAAAAAA"))
BOB = authorization(make_key(SECRET, "BBBBBBBBBBB"))


def moment(minutes_ago: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def broken_body(item_id: int = 1, **changes: object) -> dict[str, object]:
    body: dict[str, object] = {"server": "Brial", "item_id": item_id, "quantity": 2, "coefficient": 0.5,
                               "runes": [[10, 3], [11, 1]], "observed_at": moment()}
    body.update(changes)
    return body


def pet_body(pet_item_id: int = 1, **changes: object) -> dict[str, object]:
    state = {"level": 5, "experience": 100, "experience_max": 200, "prospection": 10}
    body: dict[str, object] = {"server": "Brial", "pet_item_id": pet_item_id, "resources": [[20, 4]],
                               "before": state, "after": {**state, "experience": 150}, "observed_at": moment()}
    body.update(changes)
    return body


@pytest.mark.parametrize("path, body", [("brisages", broken_body), ("familiers", pet_body)])
def test_events_are_sent_then_seen_by_the_other_player_only(client: TestClient, path: str, body) -> None:
    assert client.post(f"/{path}", json={"events": [body(1)]}, headers=ALICE).json() == {"accepted": 1, "duplicates": 0}
    assert client.post(f"/{path}", json={"events": [body(1)]}, headers=ALICE).json() == {"accepted": 0, "duplicates": 1}
    assert client.get(f"/{path}?since=0&limit=10", headers=ALICE).json()["events"] == []
    seen = client.get(f"/{path}?since=0&limit=10", headers=BOB).json()
    assert [event["key_id"] for event in seen["events"]] == ["AAAAAAAAAAA"] and seen["next"] == seen["events"][-1]["seq"]


@pytest.mark.parametrize("path, body", [("brisages", broken_body), ("familiers", pet_body)])
def test_mine_returns_only_the_callers_events(client: TestClient, path: str, body) -> None:
    client.post(f"/{path}", json={"events": [body(1)]}, headers=ALICE)
    client.post(f"/{path}", json={"events": [body(2)]}, headers=BOB)
    mine = client.get(f"/{path}/mine?after=0&limit=10", headers=ALICE).json()["events"]
    assert [event["key_id"] for event in mine] == ["AAAAAAAAAAA"]


@pytest.mark.parametrize("path", ["brisages", "familiers", "brisages/mine", "familiers/mine"])
def test_events_routes_need_a_key(client: TestClient, path: str) -> None:
    assert client.get(f"/{path}?since=0&limit=1&after=0").status_code == 401


@pytest.mark.parametrize("change", [
    {"quantity": 0}, {"coefficient": -0.1}, {"coefficient": 11.0}, {"item_id": 0}, {"server": "=cmd"},
    {"runes": [[1, 2, 3]]}, {"runes": [[0, 1]]}, {"runes": [[1, 0]]}, {"runes": [[1, 1]] * 41},
    {"observed_at": "2020-01-01T00:00:00Z"}, {"extra": 1}, {"quantity": True}, {"runes": "abc"},
])
def test_a_bad_broken_item_is_refused(client: TestClient, change: dict[str, object]) -> None:
    response = client.post("/brisages", json={"events": [broken_body(**change)]}, headers=ALICE)
    assert response.status_code == 422


@pytest.mark.parametrize("change", [
    {"pet_item_id": 0}, {"resources": []}, {"resources": [[1, 0]]}, {"extra": 1},
    {"before": {"level": -1, "experience": 1, "experience_max": 1, "prospection": 1}},
    {"before": {"level": 1}}, {"after": {"level": 1, "experience": 2**60, "experience_max": 1, "prospection": 1}},
])
def test_a_bad_pet_feeding_is_refused(client: TestClient, change: dict[str, object]) -> None:
    assert client.post("/familiers", json={"events": [pet_body(**change)]}, headers=ALICE).status_code == 422


def test_unknown_pet_levels_may_be_null(client: TestClient) -> None:
    unknown = {"level": None, "experience": None, "experience_max": None, "prospection": None}
    response = client.post("/familiers", json={"events": [pet_body(before=unknown)]}, headers=ALICE)
    assert response.status_code == 200


def test_an_empty_or_huge_batch_is_refused(client: TestClient) -> None:
    assert client.post("/brisages", json={"events": []}, headers=ALICE).status_code == 422
    assert client.post("/brisages", json={"events": [broken_body()] * 2001}, headers=ALICE).status_code == 422


def test_a_breaking_without_any_rune_is_accepted(client: TestClient) -> None:
    response = client.post("/brisages", json={"events": [broken_body(runes=[])]}, headers=ALICE)
    assert response.status_code == 200 and response.json()["accepted"] == 1


def manual_body(item_id: int = 5, units: int = 10, experience: int = 50, minutes_ago: int = 1) -> dict[str, object]:
    return {"item_id": item_id, "units": units, "experience": experience, "observed_at": moment(minutes_ago)}


def test_typed_experience_is_shared_and_the_latest_entry_replaces_the_previous_one(client: TestClient) -> None:
    client.post("/saisies", json={"events": [manual_body(units=10, experience=50, minutes_ago=5)]}, headers=ALICE)
    client.post("/saisies", json={"events": [manual_body(units=30, experience=90, minutes_ago=1)]}, headers=ALICE)
    seen = client.get("/saisies?since=0&limit=100", headers=BOB).json()["events"]
    assert [(event["item_id"], event["units"], event["experience"]) for event in seen] == [(5, 30, 90)]
    assert client.get("/saisies?since=0&limit=100", headers=ALICE).json()["events"] == []
    own = client.get("/saisies/mine?after=0&limit=100", headers=ALICE).json()["events"]
    assert [(event["units"], event["experience"]) for event in own] == [(30, 90)]


def test_typed_experience_can_be_cleared_with_zeros_and_bad_values_are_refused(client: TestClient) -> None:
    assert client.post("/saisies", json={"events": [manual_body(units=0, experience=0)]}, headers=ALICE).status_code == 200
    for change in ({"item_id": 0}, {"units": -1}, {"experience": 2_000_000_000}, {"extra": 1}):
        body = {**manual_body(), **change}
        assert client.post("/saisies", json={"events": [body]}, headers=ALICE).status_code == 422
