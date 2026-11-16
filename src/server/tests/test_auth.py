"""Bearer authentication of the HTTP application (RFC 6750) with signed, revocable keys."""

import logging

import pytest
from fastapi.testclient import TestClient

from helpers import OTHER_SECRET, SECRET, authorization
from keyserver.auth import bearer_token
from keyserver.revocations import RevocationStore
from keyserver.signed_keys import make_key, new_key_id

@pytest.mark.parametrize("header, expected", [
    ("Bearer abc", "abc"), ("bearer abc", "abc"), ("BEARER abc", "abc"),
    (None, None), ("", None), ("Bearer", None), ("Bearer ", None), ("Basic abc", None),
    ("Bearer a b", None), ("Bearer  abc", None), (" Bearer abc", None), ("Bearerabc", None),
])
def test_bearer_token_parsing(header: str | None, expected: str | None) -> None:
    assert bearer_token(header) == expected


def test_valid_key_gets_200(client: TestClient) -> None:
    response = client.get("/check", headers=authorization(make_key(SECRET, new_key_id())))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_malformed_tampered_and_revoked_keys_get_the_same_401(
        client: TestClient, revocations: RevocationStore) -> None:
    good = make_key(SECRET, "AAAAAAAAAAA")
    revoked_id = "BBBBBBBBBBB"
    revocations.revoke(revoked_id)
    attempts = [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic abc"},
        authorization(""),
        authorization(good[:-1]),
        authorization(good[:-1] + ("B" if good[-1] != "B" else "C")),
        authorization(make_key(OTHER_SECRET, "AAAAAAAAAAA")),
        authorization(make_key(SECRET, revoked_id)),
        authorization("x" * 10_000),
    ]
    responses = [client.get("/check", headers=headers) for headers in attempts]
    assert {response.status_code for response in responses} == {401}
    assert {response.headers["www-authenticate"] for response in responses} == {"Bearer"}
    assert len({response.text for response in responses}) == 1


def test_two_authorization_headers_are_refused(client: TestClient) -> None:
    good = make_key(SECRET, "AAAAAAAAAAA")
    response = client.get("/check", headers=[("Authorization", f"Bearer {good}"), ("Authorization", f"Bearer {good}")])
    assert response.status_code == 401


def test_revoking_takes_effect_on_the_next_request_without_restart(
        client: TestClient, revocations: RevocationStore) -> None:
    key = make_key(SECRET, "AAAAAAAAAAA")
    assert client.get("/check", headers=authorization(key)).status_code == 200
    revocations.revoke("AAAAAAAAAAA")
    assert client.get("/check", headers=authorization(key)).status_code == 401


def test_the_key_never_appears_in_the_logs(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    key = make_key(SECRET, "AAAAAAAAAAA")
    wrong = make_key(OTHER_SECRET, "CCCCCCCCCCC")
    with caplog.at_level(logging.DEBUG):
        client.get("/check", headers=authorization(key))
        client.get("/check", headers=authorization(wrong))
    assert key not in caplog.text and wrong not in caplog.text
    assert key.split(".")[2] not in caplog.text
