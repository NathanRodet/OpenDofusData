"""The revocation route: admin token only, idempotent, strict body, nothing echoed or logged."""

import logging

import pytest
from fastapi.testclient import TestClient

from helpers import KEY_ID, SECRET, authorization
from keyserver.revocations import RevocationStore
from keyserver.signed_keys import admin_token, make_key

KEY = make_key(SECRET, KEY_ID)
ADMIN = authorization(admin_token(SECRET))
JSON_HEADERS = {"Content-Type": "application/json"}


def revoke(client: TestClient, key_id: str = KEY_ID, headers: dict[str, str] | None = None):
    return client.post("/admin/revoke", json={"key_id": key_id}, headers=ADMIN if headers is None else headers)


def test_admin_route_needs_the_admin_token(client: TestClient) -> None:
    attempts = [{}, authorization("faux"), authorization(KEY), authorization(SECRET), authorization("")]
    responses = [revoke(client, headers=headers) for headers in attempts]
    assert {response.status_code for response in responses} == {401}
    assert {response.headers["www-authenticate"] for response in responses} == {"Bearer"}
    assert len({response.text for response in responses}) == 1


def test_admin_token_is_refused_on_user_routes(client: TestClient) -> None:
    assert client.get("/check", headers=ADMIN).status_code == 401


def test_revoke_makes_the_key_fail_at_once_and_a_second_revoke_is_still_200(client: TestClient) -> None:
    assert client.get("/check", headers=authorization(KEY)).status_code == 200
    first = revoke(client)
    assert (first.status_code, first.json()) == (200, {"revoked": True})
    assert client.get("/check", headers=authorization(KEY)).status_code == 401
    assert revoke(client).status_code == 200


def test_revoking_an_identifier_that_was_never_issued_is_accepted(client: TestClient,
                                                                  revocations: RevocationStore) -> None:
    assert revoke(client, "ZZZZZZZZZZZ").status_code == 200
    assert revocations.is_revoked("ZZZZZZZZZZZ")


@pytest.mark.parametrize("body", [
    {"key_id": ""}, {"key_id": "A" * 10}, {"key_id": "A" * 12}, {"key_id": "AAAAAAAAAA!"}, {"key_id": "AAAAAAAAAA\n"},
    {"key_id": 12345678901}, {"key_id": None}, {"key_id": KEY_ID, "extra": 1}, {}, [], "texte",
])
def test_invalid_bodies_are_422_and_never_echoed(client: TestClient, body: object) -> None:
    response = client.post("/admin/revoke", json=body, headers=ADMIN)
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_body"}


def test_malformed_json_is_422_and_never_echoed(client: TestClient) -> None:
    response = client.post("/admin/revoke", content=b'{"key_id": "<script>', headers={**ADMIN, **JSON_HEADERS})
    assert response.status_code == 422
    assert "script" not in response.text


def test_format_rules_apply_to_the_admin_route(client: TestClient) -> None:
    refused_method = client.delete("/admin/revoke", headers=ADMIN)
    assert (refused_method.status_code, refused_method.headers["allow"]) == (405, "POST")
    assert client.post("/admin/revoke/", json={"key_id": KEY_ID}, headers=ADMIN).status_code == 404
    wrong_type = client.post("/admin/revoke", content=b"key_id=x", headers={**ADMIN, "Content-Type": "text/plain"})
    assert wrong_type.status_code == 415


def test_only_the_exact_admin_prefix_selects_the_admin_domain(client: TestClient) -> None:
    assert client.post("/Admin/revoke", json={"key_id": KEY_ID}, headers=ADMIN).status_code == 401
    assert client.post("/Admin/revoke", json={"key_id": KEY_ID}, headers=authorization(KEY)).status_code == 404
    assert client.get("/admin", headers=authorization(KEY)).status_code == 401


def test_neither_the_key_nor_the_token_nor_the_secret_appears_in_the_logs(
        client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    token = admin_token(SECRET)
    with caplog.at_level(logging.DEBUG):
        revoke(client)
        revoke(client, headers=authorization(KEY))
        client.get("/check", headers=ADMIN)
    for private in (KEY, token, SECRET, KEY.split(".")[2]):
        assert private not in caplog.text
