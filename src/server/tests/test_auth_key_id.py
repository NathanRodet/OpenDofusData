"""The identifier of the verified key reaches the routes through the ASGI scope (never the full key)."""

import asyncio

from helpers import KEY_ID, SECRET, authorization
from keyserver.auth import BearerAuthMiddleware, KeyVerifier
from keyserver.revocations import open_revocations
from keyserver.signed_keys import admin_token, make_key


def run_request(path: str, headers: dict[str, str], revoked: tuple[str, ...] = ()) -> tuple[list[dict], list[dict]]:
    """Send one request through the middleware; returns (scopes seen by the inner app, messages sent back)."""
    store = open_revocations(":memory:")
    for key_id in revoked:
        store.revoke(key_id)
    seen: list[dict] = []
    sent: list[dict] = []

    async def inner(scope, receive, send) -> None:
        seen.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = BearerAuthMiddleware(inner, KeyVerifier(SECRET, store), admin_token(SECRET))
    scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()]}

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    store.close()
    return seen, sent


def test_authorised_user_request_carries_its_key_id() -> None:
    seen, _ = run_request("/check", authorization(make_key(SECRET, KEY_ID)))
    assert seen[0]["state"]["key_id"] == KEY_ID


def test_the_full_key_is_never_put_in_the_scope_state() -> None:
    key = make_key(SECRET, KEY_ID)
    seen, _ = run_request("/check", authorization(key))
    assert key not in repr(seen[0]["state"])


def test_admin_token_request_has_no_key_id() -> None:
    seen, _ = run_request("/admin/revoke", authorization(admin_token(SECRET)))
    assert "key_id" not in seen[0].get("state", {})


def test_rejected_requests_never_reach_the_application() -> None:
    seen, sent = run_request("/check", authorization(make_key(SECRET, KEY_ID)), revoked=(KEY_ID,))
    assert seen == []
    assert sent[0]["status"] == 401
