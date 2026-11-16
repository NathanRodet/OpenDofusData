"""The guard middlewares: body limit, then authentication, then request format."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from helpers import authorization, KEY_ID, SECRET
from keyserver.guards import BodyLimitMiddleware
from keyserver.request_rules import MAX_BODY_BYTES
from keyserver.signed_keys import admin_token, make_key

KEY = make_key(SECRET, KEY_ID)
TWO_MEBIBYTES = 2 * 1024 * 1024


def run_asgi(app, headers: list[tuple[bytes, bytes]], chunks: list[bytes]) -> tuple[list[dict], int]:
    """Drive an ASGI app by hand; returns what it sent and how many body chunks it read."""
    sent: list[dict] = []
    reads = []
    queue = list(chunks)

    async def receive() -> dict:
        reads.append(1)
        if queue:
            return {"type": "http.request", "body": queue.pop(0), "more_body": bool(queue)}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/check", "raw_path": b"/check", "query_string": b"",
             "headers": headers}
    asyncio.run(app(scope, receive, send))
    return sent, len(reads)


async def reading_app(scope, receive, send) -> None:
    """An inner app that reads the whole body, then answers 200."""
    more = True
    while more:
        message = await receive()
        more = message.get("more_body", False)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def status_of(sent: list[dict]) -> int:
    return next(message["status"] for message in sent if message["type"] == "http.response.start")


def test_oversized_content_length_is_413_before_the_body_is_read() -> None:
    headers = [(b"content-length", str(TWO_MEBIBYTES).encode())]
    sent, reads = run_asgi(BodyLimitMiddleware(reading_app, MAX_BODY_BYTES), headers, [b"x"])
    assert status_of(sent) == 413
    assert reads == 0


def test_streamed_body_without_length_over_the_limit_is_413() -> None:
    chunks = [b"x" * 600_000, b"x" * 600_000, b"x" * 10]
    sent, _ = run_asgi(BodyLimitMiddleware(reading_app, MAX_BODY_BYTES), [], chunks)
    assert status_of(sent) == 413


def test_a_body_within_the_limit_passes() -> None:
    sent, _ = run_asgi(BodyLimitMiddleware(reading_app, MAX_BODY_BYTES), [(b"content-length", b"3")], [b"abc"])
    assert status_of(sent) == 200


def test_a_malformed_content_length_is_400() -> None:
    sent, _ = run_asgi(BodyLimitMiddleware(reading_app, MAX_BODY_BYTES), [(b"content-length", b"abc")], [])
    assert status_of(sent) == 400


def test_the_full_application_answers_413_to_a_huge_declared_body(client: TestClient) -> None:
    response = client.post("/check", content=b"x", headers={"Content-Length": str(TWO_MEBIBYTES), **authorization(KEY)})
    assert response.status_code == 413


@pytest.mark.parametrize("method, path", [
    ("GET", "/inconnu"), ("GET", "/check/"), ("DELETE", "/check"), ("POST", "/check"), ("GET", "/admin/anything"),
    ("PUT", "/"), ("OPTIONS", "/check"),
])
def test_without_a_key_every_path_and_method_gets_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, content=b"{}", headers={"Content-Type": "application/json"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_with_a_key_an_unknown_path_is_404_and_a_wrong_method_is_405_with_allow(client: TestClient) -> None:
    assert client.get("/inconnu", headers=authorization(KEY)).status_code == 404
    response = client.delete("/check", headers=authorization(KEY))
    assert response.status_code == 405
    assert response.headers["allow"] == "GET"


def test_with_a_key_an_unexpected_query_string_is_400(client: TestClient) -> None:
    assert client.get("/check?x=1", headers=authorization(KEY)).status_code == 400


def test_with_a_key_a_body_that_is_not_json_is_415(client: TestClient) -> None:
    response = client.request("POST", "/readings", content=b"x", headers={"Content-Type": "text/plain", **authorization(KEY)})
    assert response.status_code == 415


def test_path_variants_are_never_normalised_to_a_valid_route(client: TestClient) -> None:
    for path in ("/check/", "//check", "/CHECK", "/check%2F"):
        assert client.get(path, headers=authorization(KEY)).status_code == 404, path


def test_error_bodies_are_generic_and_never_echo_the_request(client: TestClient) -> None:
    hostile = "/x<script>alert(1)</script>"
    for response in (client.get(hostile, headers=authorization(KEY)), client.get(hostile)):
        assert "script" not in response.text and "alert" not in response.text
        assert response.headers["content-type"].startswith("application/json")


def test_a_valid_request_still_reaches_the_route(client: TestClient) -> None:
    response = client.get("/check", headers=authorization(KEY))
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_the_full_application_answers_413_to_a_streamed_oversized_body_on_a_real_route(client: TestClient) -> None:
    def stream():
        for _ in range(3):
            yield b"x" * 600_000

    headers = {**authorization(admin_token(SECRET)), "Content-Type": "application/json"}
    response = client.post("/admin/revoke", content=stream(), headers=headers)
    assert response.status_code == 413
    assert response.json() == {"detail": "payload_too_large"}


def test_a_content_length_with_thousands_of_digits_is_a_400_not_an_error() -> None:
    sent, _ = run_asgi(BodyLimitMiddleware(reading_app, MAX_BODY_BYTES), [(b"content-length", b"9" * 5000)], [])
    assert status_of(sent) == 400
