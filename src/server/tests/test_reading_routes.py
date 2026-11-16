"""The reading routes: send (POST), changes and latest page (GET), authentication, strict inputs, no key leak."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from helpers import SECRET, authorization
from keyserver.readings_store import ReadingStore
from keyserver.revocations import RevocationStore
from keyserver.schemas import Reading
from keyserver.signed_keys import admin_token, make_key

ALICE_ID = "AAAAAAAAAAA"
BOB_ID = "BBBBBBBBBBB"
ALICE = authorization(make_key(SECRET, ALICE_ID))
BOB = authorization(make_key(SECRET, BOB_ID))
PAGE_LIMIT = 2000


def reading_body(item_id: int = 1, price: int = 100, **changes: object) -> dict[str, object]:
    moment = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body: dict[str, object] = {"server": "Brial", "item_id": item_id, "lot_size": 1, "price": price,
                               "observed_at": moment}
    body.update(changes)
    return body


def send(client: TestClient, headers: dict[str, str], *bodies: dict[str, object]):
    return client.post("/readings", json={"readings": list(bodies)}, headers=headers)


def test_post_readings_stores_and_reports_counts(client: TestClient) -> None:
    response = send(client, ALICE, reading_body(1), reading_body(2))
    assert (response.status_code, response.json()) == (200, {"accepted": 2, "duplicates": 0})


def test_post_same_batch_twice_reports_duplicates(client: TestClient) -> None:
    body = reading_body(1)
    send(client, ALICE, body)
    assert send(client, ALICE, body).json() == {"accepted": 0, "duplicates": 1}


def post_call(client: TestClient, headers: dict[str, str]):
    return client.post("/readings", json={"readings": [reading_body()]}, headers=headers)


def changes_call(client: TestClient, headers: dict[str, str]):
    return client.get("/readings?since=0&limit=10", headers=headers)


def mine_call(client: TestClient, headers: dict[str, str]):
    return client.get("/readings/mine?after=0&limit=10", headers=headers)


def latest_call(client: TestClient, headers: dict[str, str]):
    return client.get("/readings/latest?after=0&limit=10", headers=headers)


@pytest.mark.parametrize("call", [post_call, changes_call, latest_call, mine_call])
def test_reading_routes_require_a_user_key(client: TestClient, revocations: RevocationStore, call) -> None:
    revoked_id = "RRRRRRRRRRR"
    revocations.revoke(revoked_id)
    attempts = [{}, authorization("faux"), authorization(admin_token(SECRET)),
                authorization(make_key(SECRET, revoked_id))]
    assert {call(client, headers).status_code for headers in attempts} == {401}
    assert call(client, ALICE).status_code == 200


@pytest.mark.parametrize("body", [
    {"readings": [{**reading_body(), "extra": 1}]}, {"readings": [reading_body(lot_size=7)]},
    {"readings": [reading_body(price=0)]}, {"readings": []}, {"readings": [reading_body()] * 2001},
    {"readings": [reading_body()], "extra": 1}, [], {},
])
def test_post_readings_rejects_invalid_body(client: TestClient, body: object) -> None:
    response = client.post("/readings", json=body, headers=ALICE)
    assert (response.status_code, response.json()) == (422, {"detail": "invalid_body"})


def test_get_readings_returns_other_keys_readings_with_seq_key_id_and_next(client: TestClient) -> None:
    send(client, BOB, reading_body(1, 111), reading_body(2, 222))
    answer = changes_call(client, ALICE).json()
    assert [item["price"] for item in answer["readings"]] == [111, 222]
    assert {item["key_id"] for item in answer["readings"]} == {BOB_ID}
    assert set(answer["readings"][0]) == {"seq", "key_id", "server", "item_id", "lot_size", "price", "observed_at"}
    assert answer["next"] == answer["readings"][-1]["seq"]


def test_get_readings_next_is_since_when_nothing_is_new(client: TestClient) -> None:
    assert client.get("/readings?since=7&limit=10", headers=ALICE).json() == {"readings": [], "next": 7}


def test_get_readings_does_not_return_own_readings(client: TestClient) -> None:
    send(client, ALICE, reading_body(1))
    assert changes_call(client, ALICE).json()["readings"] == []


@pytest.mark.parametrize("query", ["", "?since=0", "?limit=10", "?since=0&limit=0", "?since=0&limit=2001"])
def test_get_readings_rejects_missing_or_out_of_range_parameters(client: TestClient, query: str) -> None:
    response = client.get(f"/readings{query}", headers=ALICE)
    assert response.status_code in (400, 422)
    assert "since" not in response.text


def test_latest_pages_until_done_and_reports_as_of(client: TestClient) -> None:
    send(client, BOB, *[reading_body(number) for number in range(1, 6)])
    first = client.get("/readings/latest?after=0&limit=3", headers=ALICE).json()
    assert (len(first["readings"]), first["done"]) == (3, False)
    second = client.get(f"/readings/latest?after={first['next']}&limit=3", headers=ALICE).json()
    assert (len(second["readings"]), second["done"]) == (2, True)
    assert first["as_of"] == second["as_of"] == 5


def test_returned_key_id_is_the_eleven_character_id_never_the_full_key(client: TestClient) -> None:
    send(client, BOB, reading_body(1))
    text = changes_call(client, ALICE).text
    signature = make_key(SECRET, BOB_ID).split(".")[-1]
    assert BOB_ID in text
    assert "odk1" not in text
    assert signature not in text


def test_full_page_of_2000_readings_is_served_whole(client: TestClient, readings: ReadingStore) -> None:
    moment = datetime.now(timezone.utc) - timedelta(minutes=1)
    readings.add_batch(BOB_ID, [Reading.model_construct(server="Brial", item_id=number, lot_size=1000, price=10**9,
                                                         observed_at=moment) for number in range(1, PAGE_LIMIT + 1)])
    response = client.get(f"/readings?since=0&limit={PAGE_LIMIT}", headers=ALICE)
    assert response.status_code == 200
    assert len(response.json()["readings"]) == PAGE_LIMIT
    assert len(response.content) > 200_000


def test_as_of_is_read_before_the_page_so_a_concurrent_reading_is_never_skipped(client: TestClient,
                                                                                readings: ReadingStore,
                                                                                monkeypatch) -> None:
    send(client, BOB, reading_body(1))
    original = readings.latest_page

    def page_then_a_new_reading_arrives(*arguments):
        page = original(*arguments)
        send(client, BOB, reading_body(2))  # committed between the page query and the end of the request
        return page

    monkeypatch.setattr(readings, "latest_page", page_then_a_new_reading_arrives)
    answer = client.get("/readings/latest?after=0&limit=10", headers=ALICE).json()
    newest = readings.highest_seq()
    assert answer["as_of"] < newest  # the reading that arrived after the page must be fetched by the next /readings call


def test_mine_returns_only_the_readings_of_the_calling_key(client: TestClient) -> None:
    send(client, ALICE, reading_body(1), reading_body(2))
    send(client, BOB, reading_body(3))
    answer = client.get("/readings/mine?after=0&limit=10", headers=ALICE).json()
    assert [item["item_id"] for item in answer["readings"]] == [1, 2]
    assert answer["next"] == answer["readings"][-1]["seq"]
    assert client.get("/readings/mine?after=0&limit=10", headers=BOB).json()["readings"][0]["item_id"] == 3
